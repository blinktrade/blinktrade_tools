import hashlib
import hmac
import time
import requests
import datetime
import random
import csv

key = 'YOUR_API_KEY'
secret = 'YOUR_API_SECRET'

BLINKTRADE_API_URL = 'https://api.blinktrade.com'
BLINKTRADE_API_VERSION = 'v1'
TIMEOUT_IN_SECONDS = 10

def send_msg(msg):
  dt = datetime.datetime.now()
  nonce = str(int((time.mktime( dt.timetuple() )  + dt.microsecond/1000000.0) * 1000000))
  signature = hmac.new( secret,  nonce, digestmod=hashlib.sha256).hexdigest()
  headers = {
    'user-agent': 'blinktrade_tools/0.1',
    'Content-Type': 'application/json',
    'APIKey': key,
    'Nonce': nonce,
    'Signature': signature
  }
  url = '%s/tapi/%s/message' % (BLINKTRADE_API_URL, BLINKTRADE_API_VERSION)
  return requests.post(url, json=msg, verify=True, headers=headers).json()

def get_balances():
  msg = {
    "MsgType": "U2",    # Balance Request
    "BalanceReqID": 1   # An ID assigned by you. It can be any number.  The response message associated with this request will contain the same ID.
  }
  return send_msg(msg)

def get_ledger_history():
  ledger_history = []
  still_have_records_to_read = True
  page=0
  while still_have_records_to_read:
    requestId = random.randint(1,100000)
    msg = {
      'MsgType': 'U34',
      'LedgerListReqID': requestId,
      'Page': page,
      'PageSize': 20
    }

    api_response = send_msg(msg)
    if api_response['Status'] != 200:
      return ledger_history

    api_responses = api_response['Responses']
    for response in api_responses:
      if response['MsgType'] == 'U35':
        ledger_list = response['LedgerListGrp']
        if len(ledger_list) < msg['PageSize']:
          still_have_records_to_read = False
        else:
          page += 1

        for ledger_array_record in  ledger_list:
          ledger_record = dict(zip(response['Columns'], ledger_array_record ))
          ledger_history.insert(0,ledger_record)
  return ledger_history


def generate_trade_record(record_0, record_1, balance_dict):
  if record_0['Reference'] != record_1['Reference']:
    raise RuntimeError("Invalid trade records")
  if record_0['Operation'] == record_1['Operation']:
    raise RuntimeError("Invalid trade records")

  if record_0['Operation'] == 'C' and record_0['Currency'] == 'BTC' and record_1['Operation'] == 'D':
    trade_type = 'BUY'
    exchange_rate = record_1['Amount'] / record_0['Amount'] * 1e8
    amount_btc = record_0['Amount']
    amount_fiat = record_1['Amount']
    balance_btc = record_0['Balance']
    balance_fiat = record_1['Balance']
    fiat_currency = record_1['Currency']
  elif record_0['Operation'] == 'D' and record_0['Currency'] == 'BTC' and record_1['Operation'] == 'C':
    trade_type = 'SELL'
    exchange_rate = record_1['Amount'] / record_0['Amount'] * 1e8
    amount_btc = record_0['Amount']
    amount_fiat = record_1['Amount']
    balance_btc = record_0['Balance']
    balance_fiat =  record_1['Balance']
    fiat_currency = record_1['Currency']
  elif record_1['Operation'] == 'C' and record_1['Currency'] == 'BTC' and record_0['Operation'] == 'D':
    trade_type = 'BUY'
    exchange_rate = record_0['Amount'] / record_1['Amount'] * 1e8
    amount_btc = record_1['Amount']
    amount_fiat = record_0['Amount']
    balance_btc = record_1['Balance']
    balance_fiat =  record_0['Balance']
    fiat_currency = record_0['Currency']
  elif record_1['Operation'] == 'D' and record_1['Currency'] == 'BTC' and record_0['Operation'] == 'C':
    trade_type = 'SELL'
    exchange_rate = record_0['Amount'] / record_1['Amount'] * 1e8
    amount_btc = record_1['Amount']
    amount_fiat = record_0['Amount']
    balance_btc = record_1['Balance']
    balance_fiat =  record_0['Balance']
    fiat_currency = record_0['Currency']
  else:
    raise RuntimeError("Invalid trade records")

  description = "%s %s @ %s %s" % (
    trade_type,"BTC {:,.8f}".format(amount_btc/1e8), fiat_currency,"{:,.2f} per BTC".format(exchange_rate/1e8), )

  record = {
    'Date'        : record_0['Created'] ,
    'Reference'   : record_0['LedgerID'],
    'Description' : description,
    'Operation'   : 'C' if trade_type == 'SELL' else 'D',
    'Currency'    : fiat_currency,
    'Total'       : amount_fiat/1e8 if trade_type == 'SELL' else  amount_fiat/1e8 * -1,
  }
  balance_dict['Balance' + fiat_currency] = balance_fiat/1e8
  balance_dict['BalanceBTC'] = balance_btc/1e8
  record.update(balance_dict)
  return record

def generate_record(record_0, balance_dict):
  description = record_0['Currency'] + ' '
  default_operation = ''
  if record_0['Description'] == 'D':
    description += 'DEPOSIT'
    default_operation = 'C'
  elif record_0['Description'] == 'DF':
    description += 'DEPOSIT FEE'
    default_operation = 'D'
  elif record_0['Description'] == 'B':
    description += 'BONUS'
    default_operation = 'C'
  elif record_0['Description'] == 'W':
    description += 'WITHDRAWAL'
    default_operation = 'D'
  elif record_0['Description'] == 'WF':
    description += 'WITHDRAWAL FEE'
    default_operation = 'D'
  elif record_0['Description'] == 'TF':
    description += 'TRADE FEE'
    default_operation = 'D'

  if record_0['Operation'] != default_operation:
    description += ' REFUND'

  balance_key = 'Balance' + record_0['Currency']
  record = {
    'Date'        : record_0['Created'],
    'Reference'   : record_0['LedgerID'],
    'Description' : description,
    'Currency'    : record_0['Currency'],
    'Operation'   : record_0['Operation'],
    'Total'       : record_0['Amount']/1e8 if record_0['Operation'] == 'C'  else record_0['Amount']/1e8 * -1
  }
  balance_dict[balance_key] = record_0['Balance']/1e8
  record.update(balance_dict)
  return record

def main():
  ledger_response = get_ledger_history()

  ledger_index = 0
  balance_dict = {}
  statement_records = []
  while ledger_index < len(ledger_response):
    ledger_item = ledger_response[ledger_index]
    formatted_record = {}
    if ledger_item['Description'] == 'T':
      ledger_index += 1
      next_ledger_item = ledger_response[ledger_index]

      formatted_record = generate_trade_record(ledger_item,next_ledger_item, balance_dict )
    elif ledger_item['Description'] in ('B','D','DF','W', 'WF', 'TF'):
      formatted_record = generate_record(ledger_item, balance_dict )

    statement_records.append(formatted_record)

    ledger_index += 1

  f = open('/Users/pinhopro/Dropbox/' + key + '.csv', 'wt')
  headers = ['Date', 'Reference', 'Description','Currency','Operation','Total']
  headers.extend(balance_dict.keys())
  try:
    writer = csv.DictWriter(f, fieldnames=headers)
    writer.writerow(dict( (n,n) for n in headers))
    for statement_record in statement_records:
      writer.writerow(statement_record)
  finally:
    f.close()


if __name__ == '__main__':
  main()
