import argparse
import logging
import os
import pandas as pd
import requests
import time

from datetime import datetime
from typing import Optional

logging.basicConfig(filename='downloader.log', level=logging.DEBUG)
_LOG = logging.getLogger('downloader')
_LOG.addHandler(logging.StreamHandler())

_ENDD_NYT = '20210505'
_BGND_NYT = '20160505'
_NYT_KEY = 'y4YhUyNHTG2pQzMfQ0ybnAj2LmVwigGo'


def get_meta_nyt(n_articles: int,
                 begin_date: int = _BGND_NYT,
                 end_date: int = _ENDD_NYT,
                 topics: Optional[str] = None,
                 dst_dir: Optional[str] = None) -> Optional[pd.DataFrame]:
    """
    Download meta data about NY Times news articles with its API.
    If `dst_dir` specified, meta dat is saved as csv else returned as dataframe.
    
    :param n_articles: How many articles to explore.
    :param begin_date: Start period for meta da collection.
    :param end_date: End period for meta da collection.
    :param dst_dir: Where to save meta data csv.
    """

    # Results are returned in 10-size batches.
    n_pages = (n_articles // 10) + 1
    _LOG.info(f'{n_pages} are going to be downloaded.')

    # Prepare empty dataset to save results.
    columns = [
        'abstract', 'web_url', 'snippet', 'lead_paragraph', 'source',
        'multimedia', 'headline', 'keywords', 'pub_date', 'document_type',
        'news_desk', 'section_name', 'byline', 'type_of_material', '_id',
        'word_count', 'uri'
    ]
    results = pd.DataFrame(columns=columns)

    for p in range(n_pages):
        _LOG.info(f'For page {p} download starts.')

        fq = 'type_of_material:("News")'
        if topics:
            fq = f'type_of_material:("News") AND body:({topics})'

        # Get a link for next 10 articles meta data.
        link = f'https://api.nytimes.com/svc/search/v2/articlesearch.json?fq={fq}&begin-date={begin_date}&end-date={end_date}&api-key={_NYT_KEY}&page={p}&facet=false'
        res = requests.get(link)

        try:
            assert res.status_code == 200
            # Add meta data to already saved.
            results = results.append(res.json()['response']['docs'])
        except AssertionError:
            _LOG.exception(
                f'Download failed due to status code {res.status_code}.')
        # Wait 6 seconds not to exceed requests limit.
        time.sleep(6)

    if dst_dir:
        today = str(datetime.date(datetime.now())).replace('-', '')
        dst_path = os.path.join(dst_dir, f'nyt_meta_{today}.csv')
        results.to_csv(dst_path)
        _LOG.info(f'Meta data saved as {dst_path}.')
    else:
        _LOG.info('Meta data returned as dataframe.')
        return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-n',
                        '--n_articles',
                        action='store',
                        type=int,
                        help='How many articles meta',
                        required=True)
    parser.add_argument('-d',
                        '--dst_dir',
                        action='store',
                        dest='dst_dir',
                        type=str,
                        help='Where to save meta',
                        required=True)
    parser.add_argument('-t',
                        '--topics',
                        action='store',
                        dest='topics',
                        type=str,
                        help='Topics of news',
                        required=False)
    args = parser.parse_args()
    if args.topics:
        get_meta_nyt(n_articles=args.n_articles,
                     topics=args.topics,
                     dst_dir=args.dst_dir)
    else:
        get_meta_nyt(n_articles=args.n_articles, dst_dir=args.dst_dir)