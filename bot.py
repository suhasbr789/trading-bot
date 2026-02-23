from dhanhq import dhanhq
import datetime,time,requests,pandas as pd

# ===== LOGIN =====
client_id="1107703902"
access_token="eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.eyJpc3MiOiJkaGFuIiwicGFydG5lcklkIjoiIiwiZXhwIjoxNzcxOTQzOTE4LCJpYXQiOjE3NzE4NTc1MTgsInRva2VuQ29uc3VtZXJUeXBlIjoiU0VMRiIsIndlYmhvb2tVcmwiOiIiLCJkaGFuQ2xpZW50SWQiOiIxMTA3NzAzOTAyIn0.457ClTQ6m3Dr0PLzvkSNBN7QZ2IX9kMeZkD1HwTrTelRnu8ZhBxC6bRZFIqsj7UtNEff7cUUk9PO1p4bapjavQ"
dhan=dhanhq(client_id,access_token)

# ===== TELEGRAM =====
BOT_TOKEN="8311404002:AAHQQTDkAS7gu7aU5E98qPqoRNxYWHvv1z4"
CHAT_ID="7354687306"

def send(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                      data={"chat_id":CHAT_ID,"text":msg})
    except: pass

# ===== TELEGRAM ENGINE =====
last_update=None
BOT_RUNNING=True

def get_cmd():
    global last_update
    try:
        r=requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates").json()
        if r["result"]:
            upd=r["result"][-1]
            if "message" in upd:
                if last_update!=upd["update_id"]:
                    last_update=upd["update_id"]
                    return upd["message"]["text"].upper()
    except: pass
    return None

# ===== SETTINGS =====
STRIKE_STEP=50
BUFFER=0.000015
TRADED=False
sec=None
symbol=None
sl=None
entry_time=None
direction=None

# ===== CANDLE =====
def candle():
    data=dhan.historical_minute_data(
        security_id="13",exchange_segment="IDX_I",
        interval="1",
        from_date=datetime.date.today().strftime("%Y-%m-%d"),
        to_date=datetime.date.today().strftime("%Y-%m-%d")
    )
    df=pd.DataFrame(data['data'])
    return df.iloc[-1]

# ===== ATM =====
def atm(p): return round(p/STRIKE_STEP)*STRIKE_STEP

# ===== EXPIRY =====
def expiry():
    t=datetime.date.today()
    th=t+datetime.timedelta((3-t.weekday())%7)
    return th.strftime("%d%b").upper()

# ===== SECURITY FINDER =====
def find_sec(strike,opt):
    chain=dhan.option_chain(security_id="13",exchange_segment="IDX_I")
    ex=expiry()
    for i in chain['data']:
        ts=i['trading_symbol']
        if str(strike) in ts and opt in ts and ex in ts:
            return i['security_id'],ts
    return None,None

# ===== ORDER =====
def buy(s): dhan.place_order(security_id=s,exchange_segment="NFO",transaction_type="BUY",quantity=50,order_type="MARKET",product_type="INTRADAY")
def sell(s): dhan.place_order(security_id=s,exchange_segment="NFO",transaction_type="SELL",quantity=50,order_type="MARKET",product_type="INTRADAY")

send("BOT STARTED")

# ===== MAIN LOOP =====
while True:
    try:
        now=datetime.datetime.now()

        # TELEGRAM
        cmd=get_cmd()
        if cmd:
            if cmd=="STOP":
                BOT_RUNNING=False; send("BOT STOPPED")
            if cmd=="START":
                BOT_RUNNING=True; send("BOT STARTED")
            if cmd=="STATUS":
                send(f"BOT:{BOT_RUNNING} TRADE:{TRADED}")
            if cmd=="PANIC":
                if TRADED: sell(sec)
                TRADED=False; send("PANIC CLOSE")

        # ENTRY
        if BOT_RUNNING and now.hour==15 and now.minute==0 and not TRADED:
            time.sleep(65)
            c=candle()

            op,lo,hi=float(c['open']),float(c['low']),float(c['high'])
            buf=op*BUFFER
            a=atm(op)

            if abs(op-lo)<=buf:
                strike=a-STRIKE_STEP
                sec,symbol=find_sec(strike,"CE")
                if sec:
                    buy(sec)
                    sl=lo
                    direction="LONG"
                    entry_time=datetime.datetime.now()
                    TRADED=True
                    send(f"ENTRY LONG {symbol}")

            elif abs(op-hi)<=buf:
                strike=a+STRIKE_STEP
                sec,symbol=find_sec(strike,"PE")
                if sec:
                    buy(sec)
                    sl=hi
                    direction="SHORT"
                    entry_time=datetime.datetime.now()
                    TRADED=True
                    send(f"ENTRY SHORT {symbol}")

        # MONITOR
        if TRADED:
            c=candle()
            price=float(c['close'])

            if direction=="LONG" and price<=sl:
                sell(sec); TRADED=False; send("SL HIT LONG")

            if direction=="SHORT" and price>=sl:
                sell(sec); TRADED=False; send("SL HIT SHORT")

            if (datetime.datetime.now()-entry_time).seconds>900:
                sell(sec); TRADED=False; send("TIME EXIT")

        time.sleep(5)

    except Exception as e:
        send(f"ERROR {e}")
        time.sleep(5)
