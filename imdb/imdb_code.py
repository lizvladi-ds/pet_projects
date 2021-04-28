import aiohttp
import asyncio
import imdb_helper_functions as imdbh
import logging
import queue
import re
import requests
from bs4 import BeautifulSoup
from collections import namedtuple
from math import ceil
from typing import List, Optional, Union, Set, Tuple

_NOT_FILMS = ["Series", "Short", "Self", "Video", "TV Movie", "TV Special", "Voice", "Singer"]
_DISTANCE_LIMIT = 3
_SEM_BATCH = 20
_ASYNC_BATCH = 20


logging.basicConfig(filename='parser.log', level=logging.INFO)
_LOG = logging.getLogger()
_LOG.addHandler(logging.StreamHandler())


async def get_actors_by_movie_soup(
        cast_page_soup: BeautifulSoup,
        num_of_actors_limit: Optional[int] = None) -> List[List[str]]:
    """
    Get list of (actor name, actor url) tuples for one movie.

    :param cast_page_soup: Soup of movie page.
    :param num_of_actors_limit: How many actors to return.
    :return: Actors tuples for actors from whole/truncated actors list on movie page.
    """
    actors = []
    Actors = namedtuple("Actors", ["name", "url"])
    table = cast_page_soup.find("table", {"class": "cast_list"})
    if table:
        for td in table.find_all("td", {"class": "primary_photo"},
                                 limit=num_of_actors_limit):
            try:
                for a_tag in td.find_all("a"):
                    name = a_tag.find("img").get("title")
                    href = a_tag.get("href")
                    actors.append(Actors(name, f"https://www.imdb.com{href}"))
            except AttributeError:
                continue
    return actors


async def get_movies_by_actor_soup(
        actor_page_soup: BeautifulSoup,
        num_of_movies_limit: Optional[int] = None) -> List[List[str]]:
    """
    Get list of (movie name, movie url) tuples for one actor.

    :param actor_page_soup: Soup of actor page.
    :param num_of_movies_limit: How many movies to return.
    :return: Movies tuples for actors from whole/truncated movies list on actor page.
    """
    Movies = namedtuple("Movies", ["name", "url"])
    movies = []
    movies_seen = set()
    if actor_page_soup.find("a", {"href": "#actress"}):
        gender = "actress"
    else:
        gender = "actor"
    table = actor_page_soup.find_all("div", id=re.compile(f"^{gender}-"))
    for row in table:
        in_prod = False
        not_film = False
        # Check if not a film.
        if any(substring.lower() in row.text.lower()
               for substring in _NOT_FILMS):
            not_film = True
        # Check if film is still in production.
        if row.find("a", {"class": "in_production"}):
            in_prod = True
        if row.find("b"):
            name = row.find("a").text
            href = row.find("a").get("href")
            # Append to results only those movies that are not in prod or not films.
            if (in_prod is False) and (not_film is
                                       False) and (name not in movies_seen):
                movies.append(
                    Movies(name, f"https://www.imdb.com{href}fullcredits"))
            movies_seen.add(name)
    return movies[:num_of_movies_limit]




async def get_movie_distance(actor_start_url: str, actor_end_url: str,
                             num_of_actors_limit: int, num_of_movies_limit: int) -> Union[str, int]:
    """
    Movie distance between 2 actors.

    For example,
    num_of_movies_limit = 5
    num_of_actors_limit = 5
    D.Jhonson and I.Elba both has `Fast & Furious Presents: Hobbs & Shaw`as their last 5 movies played in.
    Also, I.Elba and R.Downey Jr. both has `Avengers: Infinity War` as their last 5 movies.
    So, movie distance between D.Jhonson and R.Downey Jr. is 2.

    :param actor_start_url: One actor in pair to check distance for.
    :param actor_end_url: Another actor in pair to check distance for.
    :param num_of_actors_limit: How many last actors to look through for every movie.
    :param num_of_movies_limit: How many last movies to look through for every actor. Only movies are taken into account.
    :return: Movies distance.
    """
    actor_start_url = imdbh.prepare_path(actor_start_url)
    actor_end_url = imdbh.prepare_path(actor_end_url)
    distance = 1

    total_queue = queue.Queue()
    total_queue.put([actor_start_url])
    total_queue.put([actor_end_url])

    actors_checked, movies_checked = set(), set()
    sem = asyncio.Semaphore(_SEM_BATCH)

    actor_end_movies = await imdbh.get_urls(actor_end_url, num_of_movies_limit)
    actor_start_movies = await imdbh.get_urls(actor_start_url, num_of_movies_limit)


    async with aiohttp.ClientSession(raise_for_status=True) as session:
        while True:
            try:
                if total_queue.empty():
                    break
                if distance >= 3:
                    break

                # Forward search.
                actors_urls = total_queue.get()
                actors_urls = list(actors_urls)
                cur_actors_all = await imdbh.batch_check(actors_urls, _ASYNC_BATCH, actor_end_url, actors_checked,
                                                     movies_checked, actor_end_movies, num_of_actors_limit,
                                                     num_of_movies_limit, session, sem)
                total_queue.put(cur_actors_all)
                _LOG.info("Forward search move done.")

                # Backward search.
                actors_urls = total_queue.get()
                cur_actors_all = await imdbh.batch_check(actors_urls, _ASYNC_BATCH, actor_start_url, actors_checked,
                                                     movies_checked, actor_start_movies, num_of_actors_limit,
                                                     num_of_movies_limit, session, sem)
                total_queue.put(cur_actors_all)
                _LOG.info("Backward search move done.")
                distance += 0.5

                # print(f"DISTANCE:{distance}, {len(all_actors_to_check)}")
            except imdbh.BreakException:
                break

    if distance <= 0:
        distance = 1
    distance = ceil(distance)
    return distance


async def get_movie_descriptions_by_actor_soup(actor_page_soup: BeautifulSoup,
                                               num_of_movies_limit: Optional[int] = None) \
        -> List[str]:
    """
    Descriptions of last `num_of_movies_limit` movies for one actor.

    :param actor_page_soup: Soup of actor page.
    :param num_of_movies_limit: How many last movies to look through.
    :return: Movies descriptions.
    """
    # your code here
    descriptions = []
    movies = await get_movies_by_actor_soup(actor_page_soup, num_of_movies_limit)
    for movie in movies:
        url = imdbh.remove_fullcredits(movie.url)
        soup = imdbh.get_page_data_helper(url)
        description = soup.find("div", {"class": "summary_text"}).text.strip(" ").strip("\n").strip(" ")
        descriptions.append(description)
    return descriptions
