import random
import string

words = {}

def initWords():
    f = open('words.txt','r')
    for line in f:
        words[line[:len(line)-1]] = 1

    

def extendMap(s,m):
    chars = []
    sentences = []
    #print('extendMaps1',str(random.random()))
    for char in s:
        if char[len(char)-1] == ':':
            char = char[:len(char)-1]
        if char.lower() in string.ascii_letters + ' ' + "'":
            chars.append(char.lower())
        
    #print('extendMaps2',str(random.random()))
    for word in ''.join(chars).split(' '):
        if word in words:
            sentences.append(word)
    
    #print('extendMaps3',str(random.random()))
    for index in range(len(sentences)-1):
        if sentences[index] not in m:
            m[sentences[index]] = set()
        m[sentences[index]].add(sentences[index+1])
        
    return m


