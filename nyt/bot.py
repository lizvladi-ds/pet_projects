import datetime
import downloader as dwnldr
import logging
import nyt_parser
import re
import summarizer as smrzr

from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (Updater, CommandHandler, MessageHandler, Filters,
                          ConversationHandler, CallbackContext,
                          CallbackQueryHandler)
from typing import Dict, Tuple

logging.basicConfig(filename='bot.log', level=logging.INFO)
_LOG = logging.getLogger('bot')
_LOG.addHandler(logging.StreamHandler())

_TOKEN = '1697310098:AAFODz5aGwtD6UvYroVZ_34Y_Db09aNtRDk'
TOPICS, QTY, PERIOD, ARTICLES, BYE, ANSWER = range(6)

############################################################################################
# Helpers
############################################################################################


def _get_timeperiod(period: str) -> Tuple[str]:
    """
    Get begin and end date, knowing needed period.
    
    :param period: Either `day` or `week` or `month`.
    :return: Tuple of 2 strings with begin and end date.
    """
    today = datetime.datetime.today().strftime('%Y%m%d')
    if period == 'day':
        begin_date = datetime.date.today() - datetime.timedelta(days=1)
        begin_date = begin_date.strftime('%Y%m%d')
    elif period == 'week':
        begin_date = datetime.date.today() - datetime.timedelta(days=7)
        begin_date = begin_date.strftime('%Y%m%d')
    else:
        begin_date = datetime.date.today() - datetime.timedelta(days=30)
        begin_date = begin_date.strftime('%Y%m%d')
    return (begin_date, today)


def _prepare_topics(topics: str) -> str:
    """
    Prepare topics string. Correct spelling if needed and possible.
    
    :param topics: Desired topics.
    :return: Clean topics.
    """
    topics = ' '.join(
        smrzr.clean_text(topics,
                         stem=False,
                         replace_num=False,
                         spell_check=True))
    return topics


def get_articles(topics: str, period: str, qty: str) -> str:
    """
    Get articles' summaries for given period.
    
    :param topics: Desired topics.
    :param period: Either `day` or `week` or `month`.
    :param qty: How many articles.
    :return: Summarized articles.
    """
    # Get begin and end date of a needed period in `%Y%m%d` format.
    begin_date, end_date = _get_timeperiod(period)
    qty = int(qty)
    # Clean needed topics.
    topics = _prepare_topics(topics)
    # Get articles meta data.
    meta = dwnldr.get_meta_nyt(qty, begin_date, end_date, topics)
    if meta.shape[0] > qty:
        meta = meta.iloc[:qty]
    _LOG.info("Metadata recieved.")
    # Download articles based on its metadata.
    weblinks = meta['web_url'].tolist()
    # Parse articles' texts.
    articles = nyt_parser.parse(weblinks, None)
    _LOG.info("Articles downloaded and parsed.")
    # Get summaries of the parsed articles.
    summaries = {
        link: smrzr.svd_summary_pipeline(articles[link])
        for link in articles.keys()
    }
    _LOG.info("Summaries are ready.")
    return summaries


############################################################################################
# Chat Bot
############################################################################################


def start_callback(update: Update, _: CallbackContext) -> int:
    update.message.reply_text(
        "Hi! This is a New York Times bot. I will hold a conversation with you.\n"
        "Send /start to start talking to me.\n"
        "Send /cancel to stop talking to me.\n\n"
        "You can say me which topics are you interested in, how many articles do you "
        "want to read and for which time period and I will provide you New York Times "
        "articles' summaries based on your preferences.\n\n"
        "News on wich topics are you interested in?", )

    return TOPICS


def topics(update: Update, context: CallbackContext) -> int:
    user = update.message.from_user
    topics = update.message.text
    _LOG.info("Topics for user %s are %s", user.first_name, topics)
    context.user_data['topics'] = topics

    update.message.reply_text(
        "I see! How many articles do you want to read?"
        "Let's limit ourselves with 5 articles.", )

    return QTY


def qty(update: Update, context: CallbackContext) -> int:
    user = update.message.from_user
    qty = update.message.text
    _LOG.info("%s asked for %s articles", user.first_name, qty)
    context.user_data['qty'] = qty

    keyboard = [[InlineKeyboardButton('1 day', callback_data='day')],
                [InlineKeyboardButton('1 week', callback_data='week')],
                [InlineKeyboardButton('1 month', callback_data='month')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    update.message.reply_text("What time period are you interested in",
                              reply_markup=reply_markup)
    return PERIOD


def period(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    user = query.from_user
    period = query.data
    _LOG.info("%s asked for %s period", user.first_name, period)
    context.user_data['period'] = period

    qty, topics, period = context.user_data['qty'], context.user_data[
        'topics'], context.user_data['period']

    update.callback_query.answer()
    update.callback_query.message.edit_text(
        f"You asked for %s articles on %s for a %s. Please wait while articles' summaries are prepared.\n Are you ready to wait?\n"
        % (qty, topics, period))
    return ARTICLES


def articles(update: Update, context: CallbackContext) -> int:
    answer = update.message.text

    if re.search(r"(\bno\b|\bnot\b)", answer.lower()):
        _LOG.info("User anwsered %s. Stop conversation." % answer)
        bye_callback(update, context)
    else:
        summary(update, context)

    return ConversationHandler.END  #BYE


def summary(update: Update, context: CallbackContext) -> int:
    qty, topics, period = context.user_data['qty'], context.user_data[
        'topics'], context.user_data['period']

    # Download, parse and summarize articles.
    summaries = get_articles(topics, period, qty)
    # Prepare nice formatting.
    summaries = [
        article + f"\n source: {link}\n\n"
        for link, article in summaries.items()
    ]
    summaries_text = " ".join(summaries)
    summaries_text = "Here are the articles' summaries: \n\n" + summaries_text

    # Return summaries to the user. If length of summaries is more than 4096 chars, return several messages.
    iters = len(summaries_text) // 4096 + 1
    s = 0
    for i in range(iters):
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text=summaries_text[s:4096 * (i + 1)])
        s += 4096

    return ConversationHandler.END


def bye_callback(update: Update, _: CallbackContext) -> int:
    update.message.reply_text(
        "I hope you enjoyed the experience! See you soon!\n\n"
        "To start over run /start")

    return ConversationHandler.END


def cancel(update: Update, _: CallbackContext) -> int:
    _LOG.info("User %s canceled the conversation.",
              update.message.from_user.first_name)

    update.message.reply_text("Bye! I hope we can talk again some day.")

    return ConversationHandler.END


def main() -> None:
    # Create the Updater and pass it bot's token.
    updater = Updater(_TOKEN)

    # Get the dispatcher to register handlers.
    dispatcher = updater.dispatcher

    # Add conversation handler with the states TOPICS, PHOTO, PERIOD and ARTICLES.
    conv_handler = ConversationHandler(
        allow_reentry=True,
        entry_points=[CommandHandler('start', start_callback)],
        states={
            TOPICS: [MessageHandler(Filters.text, topics)],
            QTY: [MessageHandler(Filters.text, qty)],
            PERIOD: [CallbackQueryHandler(period)],
            ARTICLES: [MessageHandler(Filters.text, articles)]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    dispatcher.add_handler(conv_handler)

    # Start the Bot.
    updater.start_polling()

    # Run the bot until you press Ctrl-C.
    updater.idle()

    #updater.stop()


if __name__ == '__main__':
    main()