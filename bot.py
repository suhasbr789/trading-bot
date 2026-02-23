from dhanhq import dhanhq
import datetime, time, requests, pandas as pd

# ===== LOGIN =====
client_id="YOUR_CLIENT_ID"
access_token="YOUR_TOKEN"
dhan=dhanhq(client_id,access_token)

# ===== TELEGRAM =====
BOT_TOKEN="YOUR_BOT_TOKEN"
CHAT_ID="YOUR_CHAT_ID"

def send(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                      data={"chat_id":CHAT_ID,"text":msg})
    except: pass

# ===== TELEGRAM COMMAND ENGINE =====
last_update=None
BOT_RUNNING=True

def get_cmd():
    global last_update
    r=requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates").json()
    if r["result"]:
        upd=r["result"][-1]
        if last_update!=upd["update_id"]:
            last_update=upd["update_id"]
            return upd["message"]["text"].upper()
    return None

# ===== SETTINGS =====
STRIKE_STEP=50
BUFFER=0.000015
TRADED=False
symbol=None
sec=None
sl=None
entry_time=None
daily_pnl=0

# ===== CANDLE =====
def candle():
    data=dhan.historical_minute_data(
        security_id="13",exchange_segment="IDX_I",
        interval="1",
        from_date=(datetime.datetime.now()-datetime.timedelta(minutes=5)).strftime("%Y-%m-%d"),
        to_date=datetime.datetime.now().strftime("%Y-%m-%d")
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
    for i in chain['data']:
        if str(strike) in i['trading_symbol'] and opt in i['trading_symbol']:
            return i['security_id'],i['trading_symbol']
    return None,None

# ===== ORDER =====
def buy(s): dhan.place_order(security_id=s,exchange_segment="NFO",transaction_type="BUY",quantity=50,order_type="MARKET",product_type="INTRADAY")
def sell(s): dhan.place_order(security_id=s,exchange_segment="NFO",transaction_type="SELL",quantity=50,order_type="MARKET",product_type="INTRADAY")

# ===== HEARTBEAT =====
last_ping=time.time()
send("BOT STARTED")

# ===== MAIN LOOP =====
while True:
    try:
        now=datetime.datetime.now()

        # TELEGRAM COMMAND
        cmd=get_cmd()
        if cmd:
            if cmd=="STOP":
                BOT_RUNNING=False; send("BOT STOPPED")
            if cmd=="START":
                BOT_RUNNING=True; send("BOT STARTED")
            if cmd=="STATUS":
                send(f"BOT:{BOT_RUNNING} TRADE:{TRADED}")
            if cmd=="EXIT" and TRADED:
                sell(sec); TRADED=False; send("POSITION EXITED")
            if cmd=="PANIC":
                if TRADED: sell(sec)
                TRADED=False; send("PANIC CLOSE ALL")

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
                    buy(sec); sl=lo; entry_time=datetime.datetime.now(); TRADED=True
                    send(f"ENTRY LONG {symbol}")

            elif abs(op-hi)<=buf:
                strike=a+STRIKE_STEP
                sec,symbol=find_sec(strike,"PE")
                if sec:
                    buy(sec); sl=hi; entry_time=datetime.datetime.now(); TRADED=True
                    send(f"ENTRY SHORT {symbol}")

        # MONITOR
        if TRADED:
            c=candle(); price=float(c['close'])

            if price<=sl or price>=sl:
                sell(sec); TRADED=False; send(f"SL HIT {symbol}")

            if (datetime.datetime.now()-entry_time).seconds>900:
                sell(sec); TRADED=False; send(f"TIME EXIT {symbol}")

        # HEARTBEAT
        if time.time()-last_ping>600:
            send("BOT ALIVE"); last_ping=time.time()

        # DAILY SUMMARY
        if now.hour==15 and now.minute==30:
            send(f"DAILY PNL {daily_pnl}")

        time.sleep(2)

    except Exception as e:
        send(f"ERROR {e}")
        time.sleep(5)
