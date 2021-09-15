import argparse
import json
import logging
import os
import pandas as pd
import requests
import time

from bs4 import BeautifulSoup
from typing import Dict, List, Optional

logging.basicConfig(filename='parser.log', level=logging.DEBUG)
_LOG = logging.getLogger('parser')
_LOG.addHandler(logging.StreamHandler())

_NYT_DATA_PATH = 'articles.json'


def save_data(articles: Dict[str, str], path: str) -> None:
    """
    Save a batch of articles to a given file.
    
    :param articles: Dict of articles where key is article link 
    and value is article text.
    :param path: Where to save articles.
    """
    with open(path, 'r+') as file:
        data = json.load(file)
        # Add articles to the end of the file.
        data.update(articles)
        # Move pointer to the end of the file.
        file.seek(0)
        json.dump(data, file)


def parse(weblinks: List[str],
          dst_dir: Optional[str] = None) -> Optional[Dict[str, str]]:
    """
    Parse articles from the given weblinks. If no dst_dir given, return
    articles else save them to dst_dir as a json.
    
    :param weblinks: List of weblinks with articles.
    :param dst_dir: Where to save articles if needed.
    :return: Dict of articles or none.
    """

    batch_counter = 0
    n_links = len(weblinks)
    articles = {}

    for idx, link in enumerate(weblinks):
        _LOG.info(f'Weblink {link} taken.')
        batch_counter += 1

        page_data = requests.get(link, headers={'User-agent': f'my bot {idx}'})
        if page_data.status_code == 200:
            # Parse article text.
            soup = BeautifulSoup(page_data.text, 'lxml')
            article_body = soup.find('section', {'name': 'articleBody'})
            if article_body:
                articles[link] = article_body.text
                if dst_dir:
                    # If we collected 20 articleds or it's an end, write articles to file.
                    if (batch_counter == 20) or (idx == n_links - 1):
                        save_data(articles, dst_dir)
                        batch_counter = 0
                        articles = {}

            else:
                _LOG.warning('No text found.')

            time.sleep(2)

        elif page_data.status_code == 429:
            # Stop if requests quantity exceeded.
            if dst_dir:
                save_data(articles, dst_dir)
                _LOG.warning('Requests exceeded.')
                break
            else:
                return articles
        else:
            # Skip if any other problem happened.
            batch_counter -= 1
            _LOG.info(f'Error status code is {page_data.status_code}.')
            pass

    if not dst_dir:
        return articles


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-m',
                        '--meta_dir',
                        action='store',
                        dest='meta_dir',
                        type=str,
                        help='Where is meta saved',
                        required=True)
    parser.add_argument('-d',
                        '--dst_dir',
                        action='store',
                        dest='dst_dir',
                        type=str,
                        help='Where to save articles',
                        required=True)
    args = parser.parse_args()

    # Get articled weblinks from a meta data file.
    meta = pd.read_csv(args.meta_dir, usecols=['web_url'])
    weblinks = meta['web_url'].tolist()

    # If no file with articles already exists, create one.
    if not os.path.exists(args.dst_dir):
        with open(args.dst_dir, 'w') as file:
            json.dump({}, file)

    parse(weblinks, args.dst_dir)