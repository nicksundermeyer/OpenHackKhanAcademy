import csv
import difflib

def random():

	with open("C:/Users/simma/Downloads/translations_short.csv") as csvfile:
		result_file = "result.csv"
		out_file = open(result_file, "w")
		out_file.write("")
		in_file = csv.reader(csvfile, delimiter='§', quotechar='|')
		counter_true = 0
		counter_false = 0
		for row in in_file:	
			if len(row) == 0:#make sure the line in the document isn't empty
				continue
			diff = row_diff(row)
			
			#temp = all_identical(row[1:])
			if( print_mistakes(diff)== 0):
				counter_true += 1
			else:
				counter_false += 1
			out_file = open(result_file, "a")
			out_file.write('§'.join(row))
			out_file.write("§")
			#out_file.write(str(temp))#Writing out false or true
			out_file.write("\n")
		counter_total = counter_true + counter_false
		print("The percent of different translations are: ", (counter_false/counter_total)*100, 
			"The percent of same translations are: ", (counter_true/counter_total)*100)

def row_diff(row):
	"""returns a diff comparer"""
	string1 = row[1]
	#print("string1: ", string1)
	string2 = row[2]
	#print("string2: ", string2)
	diff = difflib.ndiff(string1.splitlines(keepends=True),string2.splitlines(keepends=True))
	return diff

def print_mistakes(diff):
	"""prints the number of mistakes that occured in the file"""
	outputs = nbr_of_outputs(diff)
	mistakes = 0
	if(outputs == 1):
	#ge högsta värdet
		mistakes = 0
	elif(outputs == 2):
		#ge sämsta värdet
		mistakes = 100
	else:
		mistakes = count_mistakes(diff)

	#print( mistakes)
	return mistakes


def all_identical(row):
	"""Checks if the sentences that has been translated are same"""
	if len(row) == 0:
		return True
	first = row[0]
	confirm = True

	for string in row:
		if(first.lower().strip() != string.lower().split()):
			confirm = False
	return confirm


def nbr_of_outputs(diff):
	"""Counts how many output diff gives, 1, 2 or 3(checks the grade of differences between the sentences"""
	out = open("out.txt", "w")
	out.write(''.join(diff))
	f = open("C:/Users/simma/Downloads/out.txt", "r")
	counter = 0

	for r in f:
		counter += 1
	return counter


def count_mistakes(diff):
	"""counts all the syntaxes it give with the result of diff, if there are slight differences between the sentences"""
	f = open("C:/Users/simma/Downloads/out.txt", "r")
	list = f.readline()
	
	count = 0
	for questionmark in list:
		if(questionmark == '?'):
			for mistake in list:
				if(mistake == '-' or mistake == '+'): #Kan komma en ^ 
					count += 1
		f.readline()
	return count


if __name__ == "__main__":

	random()