import math
from reportlab.pdfgen.canvas import Canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import json
import sys, getopt
from exchangeRate import get_exchange_rate
import textwrap

# get todays date in format dd/mm/yyyy
from datetime import date, timedelta
today = date.today()
today = today.strftime("%d/%m/%Y")

fontSize = 8
roundingPrecision = 2

# get the date in a week from now
a_week_from_now = date.today() + timedelta(days=30)

# Get the args dict from the json
with open('args.json') as f:
    args = json.load(f)

PRICE = "Preț Unitar (Price)"

helpMessage = '-h or --help for help\n' + \
    '-n or --invoiceNo for invoice number\n' + \
    '-s or --invoiceSeries for invoice series\n' + \
    '-d or --invoiceDate for invoice date\n' + \
    '-p or --dueDate for due date\n' + \
    '-l or --lang for language\n' + \
    '-q or --qty for quantity\n' + \
    '-c or --client for client\n' + \
    '-e or --exchange if to use exchange rate\n' + \
    '-r or --exchangeRate to specify exchange rate\n' + \
    '-t or --total for total amount\n' + \
    '-v or --provider for provider\n' + \
    '-b or --bonus whether to include bonus\n'


argsDict = {
    "invoiceNo": "",
    "invoiceSeries": "",
    "invoiceDate": today,
    "dueDate": a_week_from_now.strftime("%d/%m/%Y"),
    "lang": "ro",
    "qty": 1,
    "client": "AoPS",
    "exchange": "True",
    "exchangeRate": "",
    "total": "",
    "provider": "Paul",
    "bonus": False,
}

# join the args values into a string separated by :
keys = ":".join(args.values()) + ":h"
longopts = ("= ".join(args.keys()) + "=").split(" ") + ["help"]

# try:
opts, args = getopt.getopt(sys.argv[1:], keys, longopts)

optArgs = ['-' + x for x in keys.split(":")]
longOptArgs = ['--' + x[:-1] for x in longopts]

for opt, arg in opts:
    print(opt, arg)
    if opt in ("-h", "--help"):
        print(helpMessage)
        sys.exit()
    if opt in optArgs:
        key = longopts[optArgs.index(opt)][:-1]
        argsDict[key] = arg
    elif opt in longOptArgs:
        argsDict[opt[:-1]] = arg
# except TypeError:
#     print(helpMessage)
#     sys.exit()

pdfmetrics.registerFont(TTFont('Verdana', 'Verdana.ttf'))

# register verdana-bold as bold as well
pdfmetrics.registerFont(TTFont('Verdana-Bold', 'Verdana Bold.ttf'))

# First line centered: Invoice
# Second line centered: Series and number
# Third line: Date

def updateHeight(currentHeight):
    return currentHeight - 15


def drawTest(coordX, coordY, text, alignRight = False, limit=None):
    if limit == None:
        if not alignRight:
            canvas.drawString(coordX, coordY, text)
        else:
            canvas.drawRightString(coordX, coordY, text)
        return
    textToWrite = textwrap.wrap(text, limit)
    for line in textToWrite:
        if not alignRight:
            canvas.drawString(coordX, coordY, line)
        else:
            canvas.drawRightString(coordX, coordY, line)
        coordY = updateHeight(coordY)
    return coordY


height = 780

lang = argsDict.get("lang")

with open('provider.json') as f:
    provider = json.load(f).get(argsDict.get("provider"))

with open('clients.json') as f:
    client = json.load(f).get(argsDict.get("client"))

title = lang == "ro" and "Factură" or "Factură (Invoice)"
series = lang == "ro" and "Seria" or "Seria (Prefix)"
number = lang == "ro" and "Număr" or "Număr (Number)"
invoiceDate = lang == "ro" and "Data facturării" or "Data facturării (Invoice date)"
dueDate = lang == "ro" and "Data scadentă" or "Data scadentă (Due date)"

fileName = argsDict.get("invoiceSeries") + argsDict.get("invoiceNo") + "_" + argsDict.get("client") + ".pdf"

canvas = Canvas(fileName)

canvas.setFont("Verdana", fontSize + 4)
canvas.drawString(50, height, title)
height = updateHeight(height)
canvas.setFont("Verdana", fontSize + 2)
canvas.drawString(50, height, series + ": " + argsDict.get("invoiceSeries"))
canvas.drawRightString(550, height, number + ": " + argsDict.get("invoiceNo"))
height = updateHeight(height)
canvas.drawString(50, height, invoiceDate + ": " + argsDict.get("invoiceDate"))
canvas.drawRightString(550, height, dueDate + ": " + argsDict.get("dueDate"))
height = updateHeight(height)

# Line separator
canvas.line(50, height, 550, height)
height = updateHeight(height)


def drawClientProvider(client, provider, height):
    canvas.setFont("Verdana", fontSize)
    currHeight = height
    for key in provider.keys():
        if key[-2:] == "-B":
            canvas.setFont("Verdana-Bold", fontSize)
        else:
            canvas.setFont("Verdana", fontSize)
        canvas.drawString(50, currHeight, provider.get(key))
        currHeight = updateHeight(currHeight)

    # Line separator
    canvas.line(50, currHeight, 550, currHeight)
    currHeight = updateHeight(currHeight)

    for key in client.keys():
        if key[-2:] == "-B":
            canvas.setFont("Verdana-Bold", fontSize)
        else:
            canvas.setFont("Verdana", fontSize)
        canvas.drawString(50, currHeight, client.get(key))
        currHeight = updateHeight(currHeight)
    # currHeight = height
    
    return currHeight

height = drawClientProvider(client.get(lang), provider.get(lang), height)

# Line separator
canvas.line(50, height, 550, height)
height = updateHeight(height)

# Exchange Rate
fromCurr = client.get("curr")
toCurr = provider.get("curr")
if (fromCurr != None and toCurr != None and argsDict.get("exchange") == "True"):
    canvas.setFont("Verdana-Bold", fontSize)
    exchange_text = "Curs BNR la " + (argsDict.get("invoiceDate"))
    exchange_text_en = exchange_text + " (BNR exchange rate on " + (argsDict.get("invoiceDate") + ")")
    exchange_rate_title = (lang == "ro" and exchange_text or exchange_text_en) + ":"
    canvas.drawString(50, height, exchange_rate_title)
    height = updateHeight(height)
    exchange_rate = argsDict.get("exchangeRate") if argsDict.get("exchangeRate") != "" else get_exchange_rate(fromCurr, toCurr)
    canvas.drawString(50, height, "1 " + fromCurr + " = " + exchange_rate + " " + toCurr)
    height = updateHeight(height)

    # Line separator
    canvas.line(50, height, 550, height)
    height = updateHeight(height)
else:
    exchange_rate = 1

leftOffset = 50
canvas.setFont("Verdana-Bold", fontSize)
itemKeys = client.get("item").get(lang)

lowestHeight = height
index = 0
for key in itemKeys:
    if index == 3:
        leftOffset = 550
    lowestHeight = min(lowestHeight, drawTest(leftOffset, height, key, leftOffset == 550, 25))
    # canvas.drawString(leftOffset, height, key)
    leftOffset += 150
    index += 1
height = min(lowestHeight, updateHeight(height))

leftOffset = 50
quantity = argsDict.get("qty")

totalFunds = float(client.get("item").get("en").get(PRICE).split(" ")[0])
bonus = 0
print("Bonus: ", argsDict.get("bonus"))
if client.get("bonus") != None and argsDict.get("bonus"):
    bonus = float(client.get("bonus").get("en").get(PRICE).split(" ")[0])

expectedTotal = round((float(quantity) * totalFunds + bonus) * float(exchange_rate), roundingPrecision)
finalTotal = expectedTotal
exchange_fees = False
if argsDict.get("total") != "":
    finalTotal = argsDict.get("total")
    if float(finalTotal) != expectedTotal:
        exchange_fees = True

canvas.setFont("Verdana", fontSize)
index = 0
for key in itemKeys:
    if index == 3:
        leftOffset = 550
    value = client.get("item").get(lang).get(key)
    if value == "-":
        value = str(quantity)
    
    lowestHeight = min(lowestHeight, drawTest(leftOffset, height, value, leftOffset == 550, 25))
    # canvas.drawString(leftOffset, height,  value)
    leftOffset += 150
    index += 1

height = min(lowestHeight, updateHeight(height))

if client.get("bonus") != None and argsDict.get("bonus"):
    index = 0
    leftOffset = 50
    for key in itemKeys:
        if index == 3:
            leftOffset = 550
        value = client.get("bonus").get(lang).get(key)
        print(value)
        
        lowestHeight = min(lowestHeight, drawTest(leftOffset, height, value, leftOffset == 550, 25))
        leftOffset += 150
        index += 1

    height = min(lowestHeight, updateHeight(height))

if exchange_fees:
    text = lang == "ro" and "Comision schimb valutar" or "Exchange fees"
    canvas.setFont("Verdana-Bold", fontSize)
    canvas.drawString(50, height, text)
    canvas.drawRightString(550, height, str(round(float(finalTotal) - expectedTotal, roundingPrecision)) + " " + provider.get("curr"))
    height = updateHeight(height)

total = round((float(quantity) * totalFunds + bonus) * float(exchange_rate), roundingPrecision)
exchangeString = exchange_fees == True and " - " + str(abs(round(float(finalTotal) - expectedTotal, roundingPrecision))) + " " + provider.get("curr") or ""
totalSum = float(quantity) * totalFunds + bonus
totalString = str(round(totalSum, roundingPrecision)) + \
    " " + client.get("curr")

if argsDict.get("exchange") == "True":
    totalString += " x " + str(exchange_rate) + exchangeString + " = " + str(finalTotal) + " " + provider.get("curr")

canvas.setFont("Verdana-Bold", fontSize)
canvas.drawRightString(550, height, "Total: " + totalString)
height = updateHeight(height)

# Line separator
canvas.line(50, height, 550, height)
height = updateHeight(height)

# Payment details
canvas.setFont("Verdana-Bold", fontSize)
paymentDetails = provider.get("payment").get(lang)

for key in paymentDetails.keys():
    if key[-2:] == "-B":
        canvas.setFont("Verdana-Bold", fontSize)
    else:
        canvas.setFont("Verdana", fontSize)
    
    canvas.drawString(50, height, paymentDetails.get(key))
    height = updateHeight(height)

canvas.save()

