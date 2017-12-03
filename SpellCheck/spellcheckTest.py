# -*- coding: utf-8 -*-

import enchant
import string

# spell checker
d = enchant.Dict("sv")

# creating and opening fil
fileName = "translations.csv"
fp = open(fileName, 'r')

outFileName = "outFile.csv"
outFile = open(outFileName, 'w')

# list of non-letter symbols
charList = set(string.punctuation.replace("_", ""))

# goes through file to find translated lines 
count = 0
while count < 1000:
    count += 1
    chunk = fp.readline()
    lineWrite = chunk + "☡"
    chunk = chunk.split("☡")
    chunk[2] = chunk[2][:len(chunk[2])-1]
    
    for word in chunk[1].split():
        
        tmp = d.suggest(word)

        if not word in tmp:
            lineWrite += "(" + word + ", " + str(tmp) + ")"
    
    outFile.write(lineWrite)

fp.close()
outFile.close()