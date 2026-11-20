# name
# line height
# A
# B
# C
# D
# E
# F
# G
# H
# I
# J
# K
# L
# M
# N
# O
# P
# Q
# R
# S
# T
# U
# V
# W
# X
# Y
# Z
# a
# b
# c
# d
# e
# f
# g
# h
# i
# j
# k
# l
# m
# n
# o
# p
# q
# r
# s
# t
# u
# v
# w
# x
# y
# z
# ,
# .
# !
# ?
# -

import sys

chars = ["A","B","C","D","E","F","G","H","I","J","K","L","M","N","O","P","Q","R","S","T","U","V","W","X","Y","Z","a","b","c","d","e","f","g","h","i","j","k","l","m","n","o","p","q","r","s","t","u","v","w","x","y","z",",",".","!","?","-",]
charlines = []
name = ""
height = 0
filename = ""

def process_file(file_path):
    print(f"Processing: {file_path}")
    
    with open(file_path, "r", encoding="utf-8") as file:
        index = 0

        for line in file:
            if index == 0:
                name = line.strip()
            elif index == 1:
                height = int(line.strip())
                filename = f"{name}{height}.json"
            else:
                charlines.append(line.rstrip('\n')
                                 .replace('"',"\\\"")
                                )

            index += 1

    return filename, height
        

def create_file(filename):
    print(f"Creating: {filename}")

    with open(filename, "w") as fileout:
        fileout.write("{\n") 

        index = 0
        for char in chars:
            fileout.write(f"  \"{char}\": [\n")

            for i in range(0,height): # WRITE CHAR LINES

                if i == height - 1:
                    fileout.write(f"    \"{charlines[i + (index * height)]}\"\n")
                else:
                    fileout.write(f"    \"{charlines[i + (index * height)]}\",\n")

            if char == "-":             # LAST CHAR IN FILE, FORMAT PROPERLY
                fileout.write(f"  ]\n")
            else:
                fileout.write(f"  ],\n")

            index += 1
        
        fileout.write(f"}}")











if __name__ == "__main__":
    # sys.argv[0] is the script name; sys.argv[1:] are the dropped files
    dropped_files = sys.argv[1:]
    
    if not dropped_files:
        print("Drag and drop files onto this script to process them.")
    else:
        for file_path in dropped_files:
            processed = process_file(file_path)

            filename = processed[0]
            height = processed[1]
            create_file(filename)
            
    # input("\nPress Enter to exit...")  # Keeps the console window open to view output REMOVE AFTER
