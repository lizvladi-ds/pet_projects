import logging
#import networkx as nx
import numpy as np
import pandas as pd
import re
import string
import nltk
#nltk.download('stopwords')

from nltk import sent_tokenize
from nltk.corpus import stopwords
from nltk.stem import PorterStemmer
from nltk.tokenize import word_tokenize
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from spellchecker import SpellChecker
from typing import List, Set

logging.basicConfig(filename='summarizer.log', level=logging.DEBUG)
_LOG = logging.getLogger('summarizer')
_LOG.addHandler(logging.StreamHandler())

_STOP_WORDS = set(stopwords.words('english'))
_STOP_WORDS.update({'mr', 'mrs', 'ms', 'us'})

_PUNCT = set(string.punctuation)
_STOP_WORDS.update({'’', '—', '“', '”', ''})
_DIGIT_TOKEN = 'DIGIT'


def clean_text(sentence: str,
               stem: bool = True,
               replace_num: bool = True,
               spell_check: bool = False) -> List[str]:
    """
    Cleaning of a sentence includes:
        - lowering all words
        - stripping punctuation
        - removing stopwords
        - replcaing digits with a special token if needed
        - spelling correction if needed
        - stemming with Porter Stemmer
        
    :param sentence: One sentence text.
    :return: List of tokens.
    """
    stemmer = PorterStemmer()
    spell = SpellChecker()
    # Split sentence into tokens.
    tokens = word_tokenize(sentence.lower())
    # Strip commas and full stops from tokens, remove stopwords and punctuation.
    tokens = [
        x.strip('.').strip(',') for x in tokens
        if (x not in _PUNCT) and (x not in _STOP_WORDS)
    ]
    # Replace digits with a special token.
    if replace_num:
        tokens = [
            _DIGIT_TOKEN if
            (x.isdigit() or ((not x.isalpha()) and (',' in x))) else x
            for x in tokens
        ]
    # Correct spelling.
    if spell_check:
        tokens = [spell.correction(x) for x in tokens]
    # Stem tokens with Porter Stemmer.
    if stem:
        tokens = [stemmer.stem(x) for x in tokens]
    return tokens


def tokenize_sentences(text: str) -> List[str]:
    """
    Tokenization of a sentence includes:
        - add space after full stop if needed
        - splitting sentence by nltk tokenizer
        - additional splitting by `.“` 
        
    :param text: Original text without any cleaning.
    :return: List of sentences.
    """
    # Add space after full stop.
    text = re.sub(r'\.(?=[^ \W\d])', '. ', text)
    sentences = sent_tokenize(text)
    # Also split by `.“`
    sentences = [sentence.split('.“') for sentence in sentences]
    # Flatten list of lists of sentences.
    sentences = [item for sublist in sentences for item in sublist]
    return sentences


def get_tfidf(clean_text: str) -> pd.DataFrame:
    """
    Prepare tf-idf from text. 
        
    :param clean_text: Already cleaned text.
    :return: tf-idf table.
    """
    # Get Tf-IDF
    vectorizer = TfidfVectorizer()
    tfidf = vectorizer.fit_transform(clean_text)
    # Wrap with dataframe.
    feature_names = vectorizer.get_feature_names()
    dense = tfidf.todense()
    denselist = dense.tolist()
    df = pd.DataFrame(denselist, columns=feature_names)
    return df


def get_sentences_svd(tfidf: pd.DataFrame, top_n: float = 0.3) -> Set[int]:
    """
    Get sentences' indices for summary. 
    Sentences are chosen as the most related to first 2 topics, extracted
    with the help of SVD.
        
    :param tfidf: tf-idf matrix.
    :param top_n: Lower bound of absolute relation of a sentence to topics.
    :return: Sentences' indices for summary.
    """
    # Do SVD for the given tfidf of a text.
    u, s, vh = np.linalg.svd(tfidf, full_matrices=False)
    # Create topics-sentences matrix.
    topics_sentences = pd.DataFrame(u @ np.diag(s))
    # For first topic leave only sentences with correlation higher than top_n.
    first_topic = topics_sentences[0].apply(abs)
    first_topic_top = first_topic[first_topic >= top_n].index.tolist()
    # For second topic leave only sentences with correlation higher than top_n.
    second_topic = topics_sentences[1].apply(abs)
    second_topic_top = second_topic[second_topic >= top_n].index.tolist()
    # Get a set of chosen sentences for the first 2 topics.
    result_sent_idx = set(first_topic_top + second_topic_top)
    _LOG.info(
        f'{len(result_sent_idx)} sentences left out of {tfidf.shape[0]}.')
    result_sent_idx = sorted(result_sent_idx)
    return result_sent_idx


def svd_summary_pipeline(text: str, top_n: float = 0.3) -> str:
    """
    Get text summary, created from the original text's sentences.
        
    :param text: Raw text.
    :param top_n: Lower bound of absolute relation of a sentence to topics.
    :return: Text summary.
    """
    # Get clean text.
    sentences = tokenize_sentences(text)
    _LOG.info('Sentences tokenized.')
    cleaned_text = [' '.join(clean_text(sentence)) for sentence in sentences]
    # Get tf-idf of the text.
    tfidf = get_tfidf(cleaned_text)
    _LOG.info('TF-IDF done.')
    # Get indices of the sentences for a summary.
    result_sent_idx = get_sentences_svd(tfidf, top_n)
    # Build the summary.
    summary = ' '.join(np.array(sentences)[result_sent_idx])
    _LOG.info('Summary done.')
    return summary


def cos_summary_pipeline(text: str) -> str:
    """
    Get text summary, created from the original text's sentences based on
    average cosine similiraty of the TF-IDF of the text.
    
    The summary has a length of square root of the original text's length.
        
    :param text: Raw text.
    :return: Text summary.
    """
    # Get clean text.
    sentences = tokenize_sentences(text)
    _LOG.info('Sentences tokenized.')
    cleaned_text = [' '.join(clean_text(sentence)) for sentence in sentences]
    # Get tf-idf of the text.
    tfidf = get_tfidf(cleaned_text)
    _LOG.info('TF-IDF done.')
    # Get cosine similarity matrix.
    similarities = cosine_similarity(tfidf, tfidf)
    _LOG.info('Cosine similarity done.')
    # Define how many sentences to use in summary.
    n_sents = round(tfidf.shape[0]**0.5)
    # Find sentences with highest average cosine similarity.
    sim_avg = []
    for sentence in similarities:
        sim_avg.append(sentence.mean())
    # Prepare summary.
    top_idx = np.argsort(sim_avg)[-n_sents:]
    top_idx = sorted(top_idx)
    summary = ' '.join(np.array(sentences)[top_idx])
    _LOG.info('Summary done.')
    return summary


'''def pagerank_summary_pipeline(text: str) -> str:
    """
    Get text summary, created from the original text's sentences based on
    page rank of the cosine similiraty of the TF-IDF of the text.
    
    The summary has a length of square root of the original text's length.
        
    :param text: Raw text.
    :return: Text summary.
    """
    # Get clean text.
    sentences = tokenize_sentences(text)
    _LOG.info('Sentences tokenized.')
    cleaned_text = [' '.join(clean_text(sentence)) for sentence in sentences]
    # Get tf-idf of the text.
    tfidf = get_tfidf(cleaned_text)
    _LOG.info('TF-IDF done.')
    # Get cosine similarity matrix.
    similarities = cosine_similarity(tfidf, tfidf)
    _LOG.info('Cosine similarity done.')
    # Define how many sentences to use in summary.
    n_sents = round(tfidf.shape[0]**0.5)
    # Find sentences with highest cosine similarity based on pagerank.
    scores = nx.pagerank(nx.from_numpy_array(similarities))
    top_idx = list(
        dict(sorted(scores.items(), key=lambda item: item[1],
                    reverse=True)).keys())[:n_sents]
    top_idx = sorted(top_idx)
    # Prepare summary.
    summary = ' '.join(np.array(sentences)[top_idx])
    _LOG.info('Summary is done.')
    return summary'''