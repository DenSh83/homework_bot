import logging
import os
import sys
import time
import telegram
import exceptions
import json
import requests

from dotenv import load_dotenv
from http import HTTPStatus

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверка доступности переменных окружения."""
    return all([TELEGRAM_TOKEN, PRACTICUM_TOKEN, TELEGRAM_CHAT_ID])


def send_message(bot, message):
    """Отправка сообщения в Telegram чат."""
    try:
        logger.info('Попытка отправки сообщения')
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except Exception as error:
        logger.error('Ошибка отправки сообщения')
    else:
        logger.info('Сообщение в чат отправлено')


def get_api_answer(timestamp):
    """Отправка запроса к API."""
    params = {'from_date': timestamp}
    try:
        homework_statuses = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params
        )
        if homework_statuses.status_code == HTTPStatus.INTERNAL_SERVER_ERROR:
            raise Exception('Нет ответа от сервера')
        if homework_statuses.status_code != HTTPStatus.OK:
            raise Exception('Ошибка в коде состояния HTTP')
    except RequestException as error:
        logging.error(error)
        raise RequestException(
            'Ошибка ответа от сервера')
    return homework_statuses.json()


def check_response(response):
    """Проверка ответа сервера на корректность."""
    if not isinstance(response, dict):
        raise TypeError('Ответ не в формате словаря')
    if 'homeworks' not in response:
        raise KeyError('Данных homeworks нет в ответе')
    if 'current_date' not in response:
        raise KeyError('Данных current_date нет в ответе')
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError('От API не получен список')
    return homeworks


def parse_status(homework):
    """Проверка статуса работы, полученного в API"""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_VERDICTS:
        raise KeyError(f'Неизвестный статус {homework_status}')
    verdict = HOMEWORK_VERDICTS.get(homework_status)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical('Стоп! Отсутствуют переменные окружения')
        sys.exit(1)
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(timestamp)
            timestamp = response.get('current_date')
            logging.debug('Начало проверки ответа сервера')
            homeworks = check_response(response)
            if not homeworks:
                logging.debug('Статус не изменился')
            else:
                message = parse_status(homeworks[0])
                send_message(bot, message)
            send_message(bot, 'Пауза')
        except Exception as error:
            logging.error(error)
            message = f'Сбой в работе программы: {error}'
            if message != error_message:
                send_message(bot, message)
                error_message = message
        finally:
            time.sleep(RETRY_PERIOD)

if __name__ == '__main__':
    logger = logging.getLogger(__name__)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s, %(levelname)s, %(message)s, %(name)s',
        handlers=[logging.StreamHandler()]
    )
    main()
