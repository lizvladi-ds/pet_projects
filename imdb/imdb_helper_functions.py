import aiohttp
import asyncio
import imdb_code as imdb
import logging
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import requests
import string
import urllib.parse as urlp
from PIL import Image
from bs4 import BeautifulSoup
from pandas import DataFrame
from typing import Callable, Dict, List, Optional, Set, Tuple
from wordcloud import WordCloud

logging.basicConfig(filename='parser.log', level=logging.INFO)
_LOG = logging.getLogger()
_LOG.addHandler(logging.StreamHandler())

_ASYNC_BATCH = 20

_NLTK_STWRDS = [
    'ourselves', 'hers', 'between', 'yourself', 'but', 'again', 'there',
    'about', 'once', 'during', 'out', 'very', 'having', 'with', 'they', 'own',
    'an', 'be', 'some', 'for', 'do', 'its', 'yours', 'such', 'into', 'of',
    'most', 'itself', 'other', 'off', 'is', 's', 'am', 'or', 'who', 'as',
    'from', 'him', 'each', 'the', 'themselves', 'until', 'below', 'are', 'we',
    'these', 'your', 'his', 'through', 'don', 'nor', 'me', 'were', 'her',
    'more', 'himself', 'this', 'down', 'should', 'our', 'their', 'while',
    'above', 'both', 'up', 'to', 'ours', 'had', 'she', 'all', 'no', 'when',
    'at', 'any', 'before', 'them', 'same', 'and', 'been', 'have', 'in', 'will',
    'on', 'does', 'yourselves', 'then', 'that', 'because', 'what', 'over',
    'why', 'so', 'can', 'did', 'not', 'now', 'under', 'he', 'you', 'herself',
    'has', 'just', 'where', 'too', 'only', 'myself', 'which', 'those', 'i',
    'after', 'few', 'whom', 't', 'being', 'if', 'theirs', 'my', 'against', 'a',
    'by', 'doing', 'it', 'how', 'further', 'was', 'here', 'than', 'hes', 'shes',
    'theyre', 'outcast', 'one', 'make', 'must', 'causes', 'due', 'come', 'despite'
]


async def fetch(session: aiohttp.ClientSession, url: str) -> str:
    async with session.get(url) as response:
        assert response.status == 200, f"Response code for {url} is {code}."
        return await response.text()


class BreakException(Exception):
    pass


def get_page_data_helper(url: str) -> BeautifulSoup:
    """
    Get page soup from url.

    :param url: Page to get soup from.
    :return: Soup of a page.
    """
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "lxml")
    return soup


async def get_page_data(url: str, session: aiohttp.ClientSession, sem: asyncio.Semaphore,
                        checked: Set[str]) -> BeautifulSoup:
    """
    Get page soup from url.

    :param url: Page to get soup from.
    :param session: Client session for request.
    :param sem: Semaphore for batching requests.
    :param checked: Already checked urls.
    :return: Soup of a page.
    """
    async with sem:
        soup = ''
        if url not in checked:
            response = await fetch(session, url)
            soup = BeautifulSoup(response, "lxml")
    return soup


async def get_urls(url: str, limit:int) -> Set[str]:
    response_start_actor = requests.get(url)
    soup = BeautifulSoup(response_start_actor.text, "lxml")
    movies = await imdb.get_movies_by_actor_soup(soup, limit)
    actor_end_movies = {movie.url for movie in movies}
    return actor_end_movies


async def batch_check(actors_urls: Set[str], batch_size: int, actor_target_url:str,
                      actors_checked:Set[str], movies_checked:Set[str], actor_target_movies:Set[str],
                      num_of_actors_limit:int, num_of_movies_limit:int, session, sem) -> Set[str]:
    actors_urls = list(actors_urls)
    actors_batches = [actors_urls[i:i + batch_size] for i in range(0, len(actors_urls), batch_size)]
    for actors_batch in actors_batches:
        cur_actors_all = set()
        cur_actors_to_check, actors_checked, movies_checked = await check_actors(
            actors_batch, actor_target_url, actors_checked, movies_checked,
            actor_target_movies, num_of_actors_limit, num_of_movies_limit, session, sem)
        cur_actors_all.update(cur_actors_to_check)
    return cur_actors_all


async def check_movies(movie_urls: List[str], movies_checked: Set[str],
                       num_of_actors_limit: int, actor_end_url: str, session,
                       sem) -> Tuple[Set[str], Set[str]]:
    actors_to_check = set()
    soups = await asyncio.gather(
        *[get_page_data(movie, session, sem, movies_checked) for movie in movie_urls])
    soups = [soup for soup in soups if soup != '']
    _LOG.info("%d movie soups were extracted" % len(soups))
    actors = await asyncio.gather(*[imdb.get_actors_by_movie_soup(soup, num_of_actors_limit) for soup in soups])
    actors = [item for sublist in actors for item in sublist]
    _LOG.info("%d actors were extracted for those movie soups" % len(actors))
    urls = [actor.url for actor in actors]
    if actor_end_url in urls:
        _LOG.info("Actor match.")
        # dst += 1
        raise BreakException()
    else:
        actors_to_check.update(urls)
    movies_checked.update(movie_urls)
    return actors_to_check, movies_checked


async def check_actors(actors_urls: List[str], actor_end_url: str, actors_checked: Set[str],
                       movies_checked: Set[str], actor_end_movies: List[str], num_of_actors_limit: int,
                       num_of_movies_limit: int, session, sem) -> Tuple[Set[str], Set[str], Set[str]]:
    if actor_end_url in actors_urls:
        raise BreakException()

    all_actors_to_check = set()

    # Get all actors soups.
    soups = await asyncio.gather(
        *[get_page_data(actor, session, sem, actors_checked) for actor in actors_urls])
    soups = [soup for soup in soups if soup != '']
    # Get all movies for extracted actors soups.
    movies = await asyncio.gather(*[imdb.get_movies_by_actor_soup(soup, num_of_movies_limit) for soup in soups])
    movies = [item for sublist in movies for item in sublist]
    movie_urls = [movie.url for movie in movies]

    # If dst actor starred in the same movie as one of the current actors, break.
    if actor_end_movies.intersection(set(movie_urls)):
        _LOG.info("Movies inresection was found.")
        raise BreakException()

    # Extract movies for current actors, check for matches, extract actors from extracted movies.
    actors_to_check, movies_checked = await check_movies(
        movie_urls, movies_checked, num_of_actors_limit, actor_end_url, session, sem)
    all_actors_to_check.update(actors_to_check)
    actors_checked.update(actors_urls)

    return all_actors_to_check, actors_checked, movies_checked


def remove_fullcredits(url: str) -> str:
    """
    For url of type `www.imdb.com/title/tt8936646/fullcredit` return
    `www.imdb.com/title/tt8936646`.
    For url of type `www.imdb.com/title/tt8936646` return itself.

    :param url: Url to remove `www.imdb.com/title/tt8936646` part from.
    :return: Clean url.
    """
    if 'fullcredit' in url:
        url = ('/').join(url.split('/')[:-1])
    return url


def prepare_path(url: str) -> str:
    """
    Add `https://www.` to an imdb link.

    :param url: Url to prepare.
    :return: Url of type `https://www.imdb.com/...`.
    """
    url = urlp.urlparse(url).path
    url = urlp.urljoin('https://www.imdb.com/', url)
    return url


def plot_graph(results_df: DataFrame, dstc_to_plot: List[int]) -> None:
    """
    Plot graph with distances for all actors.

    :param results_df: Result with `actor_from`, `actor_to`, `dst` columns
    :param dstc_to_plot: Edges of which distance to show. If empty list, show all.
    """
    assert all([i in results_df.columns for i in ['actor_from', 'actor_to', 'dist']])
    # Additional preparation
    results_df['color'] = results_df['dist'].apply(lambda x: 'red' if x == 1 else 'green')
    actors_pairs = results_df[['actor_from', 'actor_to']].values
    actors_pairs = tuple([tuple(x) for x in actors_pairs])
    weights = tuple(results_df['dist'].values.tolist())
    edges_ = dict(zip(actors_pairs, weights))
    # Coloring preparation
    green = results_df[results_df['color'] == 'green'][['actor_from', 'actor_to', 'dist']].values.tolist()
    red = results_df[results_df['color'] == 'red'][['actor_from', 'actor_to', 'dist']].values.tolist()
    r, g = 'r', 'g'
    if 1 in dstc_to_plot:
        g = 'w'
    if 2 in dstc_to_plot:
        r = 'w'
    # Build Graph
    G = nx.Graph()
    for key, value in edges_.items():
        G.add_edge(key[0], key[1])
        G[key[0]][key[1]]['dist'] = value
    # Draw plot
    plt.figure(figsize=(12, 12))
    pos = nx.circular_layout(G)
    nx.draw_networkx_nodes(G, pos, node_size=1000)
    nx.draw_networkx_labels(G, pos)
    nx.draw_networkx_edges(G, pos, edgelist=red, edge_color=r, arrows=False, label='1')
    nx.draw_networkx_edges(G, pos, edgelist=green, edge_color=g, arrows=False, label='2')
    labels = nx.get_edge_attributes(G, 'dist')
    if dstc_to_plot:
        labels = {k: v for k, v in labels.items() if v in dstc_to_plot}
    nx.draw_networkx_edge_labels(G, pos, edge_labels=labels)
    plt.axis("off")
    plt.show()


def remove_punct(text):
    text = text.translate(str.maketrans('', '', string.punctuation))
    return text


def preprocess(text: str) -> List[str]:
    """
    Remove stopwords and punctuation.

    :param text: One string.
    :return: Clean words.
    """
    words = text.split()
    words = [remove_punct(word) for word in words]
    words = [word.lower() for word in words if word.lower() not in _NLTK_STWRDS]
    return words


def plot_wordcloud(descriptions: Dict[str, str]) -> None:
    """
    Show word clouds got from movies descriptions of each actor.

    :param descriptions: Actors movie descriptions merged.
    :return: Show clouds.
    """
    for name, descr in descriptions.items():
        words = preprocess(descr)
        # Plot word cloud.
        cloud_mask = np.array(Image.open("cloud.png"))
        fig, ax = plt.subplots(figsize=(10, 10))
        wordcloud = WordCloud(max_font_size=50,
                              max_words=100,
                              background_color="white",
                              mask=cloud_mask).generate(" ".join(words))
        plt.imshow(wordcloud, interpolation="bilinear")
        plt.axis("off")
        ax.set_title(name,
                     pad=20,
                     fontsize=20,
                     color="#1A5276",
                     fontweight="bold")
        plt.show()
