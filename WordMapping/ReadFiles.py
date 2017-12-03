import pickle

def run(f):
    fileArray = []
    stringArray = []
    unknownArray = []
    for line in f:
        fileArray.append(line)

    count = 0
    approvedCount = 0 
    m = {}
    for index in range(len(fileArray)):
        if '<trans-unit' in fileArray[index]:
            #m[fileArray[index+1]] = fileArray[index+2]
            src = fileArray[index+2]
            try:
                #stringArray.append(src[src.index('<source>')+8:src.index('</source>')])
                if 'approved' in fileArray[index]:
                    stringArray.append(src[src.index('>')+2:src.index('</target>')])
                    approvedCount += 1
                else:
                    unknownArray.append(src[src.index('>')+2:src.index('</target>')])
                #print(src)
                
            except:
                print('whoops')
                if 'approved' in fileArray[index]:
                    #stringArray.append(src[src.index('>')+2:])
                    approvedCount += 1
                else:
                    pass
                    #unknownArray.append(src[src.index('>')+2:])
 
                #stringArray.append(src[src.index('<source>')+8:])
            count += 1
        else:
            index += 4

    #print('approved count:',approvedCount)

    #print('String count:',count)
    return stringArray,unknownArray


def check(m,unknownStrings):
    partials = []
    goodStr = []
    stillUnknown = []
    for string in unknownStrings:
        good = True
        split = string.split(' ')
        startPart = 0
        for index in range(len(split)-1):
            if split[index] not in m or split[index+1] not in m[split[index]]:
                good = False
                if ''.join(split[0:index]) not in partials:
                    partials.append(' '.join(split[startPart:index]))
                    #print(' '.join(split[0:index]))
                    startPart = index
                    
            
        
        if good:
            goodStr.append(string)
            #print(string)
            


    #goodStrings += goodStr
    #partialStrings += partials

    return (goodStr,partials, len(unknownStrings))



def Map(m,knownStrings):
    mapping.initWords()
    for s in knownStrings:
        m = mapping.extendMap(s,m)

    return len(knownStrings)
    

def WOOHOO():
    m = {}

    goodStrings = []
    partialStrings = []
    totalStrings = 0
    learnedStringCount = 0
    testedStringCount = 0

    with open('dict.pickle','rb') as h:
        m = pickle.load(h)

    for x in range(1,11):
        if x == 11 or x == 14 or x == 46:
            continue
        f = open('DataIn/'+str(x)+'.xliff')
        print('opening file:','DataIn/'+str(x)+'.xliff')
        known, unknown = run(f)
        print('Mapping\n')
        totalStrings += Map(m,known)
        approved, partialApproved,totalStrings = check(m,unknown)
        f.close()


    #approved,partialApproved,totalStrings = check(m,['hello there friend','the functions is','we multiply the numbers','Alex joggar $1000\\, \\text{m}$.'])
    
        #pickle.dump(m,h,protocol=pickle.HIGHEST_PROTOCOL)

    #print('Learned:',numLearningStrings)
    #print('Compared:',len(strings)-numLearningStrings)
    print('-----------------')
    print(len(m))
    print('Unknown -> Approved:',len(approved)/totalStrings)
    print('Partial Segments Approved::',len(partialApproved))
    print(approved)



if __name__ == "__main__":
    import mapping
    #m = {}
    #for x in range(1,3):
        #f = open('DataIn/'+str(x)+'.xliff')
        #print('opening file:','DataIn/'+str(x)+'.xliff')
        #known, unknown = run(f)
        #Map(m,known,unknown)
    WOOHOO()

