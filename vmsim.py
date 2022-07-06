#!/usr/bin/env python3
import argparse
import math
import sys
import cProfile
import re

class virtual_memory_sim():
    '''
        Virtual memory simulator
        Run through the memory references of the trace file
        Decide the action taken for each address 
            * memory hit
            * page fault with no eviction
            * page fault and evict clean page
            * page fault and evict dirty page
            
        After dealing with all the memory references for both simulated processes
        print out summary statistics in the following format
    '''
    def __init__(self):
        self.parser = argparse.ArgumentParser()
        self.algorithm = ''
        self.frames = 0
        self.page_size = 0
        self.memory_split = ''
        self.tracefile = ''
        self.memory_accesses = 0
        self.page_faults = 0
        self.disk_writes = 0
        self.offset = None

    def parse_args(self):
        '''
           parses the command line arguements and subcommands using argparse.py
        '''
        self.parser.add_argument('-a', '--algorithm',     type=str, choices = ['opt', 'lru'])
        self.parser.add_argument('-n', '--numframes',  type=int)
        self.parser.add_argument('-p', '--pagesize',   type=int)
        self.parser.add_argument('-s', '--memorysplit',type=str)
        self.parser.add_argument('tracefile', type=str)
        contents = self.parser.parse_args()
        if (contents.algorithm != '' ):
            self.algorithm = contents.algorithm
        if (contents.numframes != 0):
            self.frames = contents.numframes
        if (contents.pagesize != 0):  
            self.page_size = contents.pagesize
            self.offset = int(math.log2(contents.pagesize)) + 10
        if (contents.memorysplit != ''):
            self.memory_split = contents.memorysplit
        if (contents.tracefile != ''):
            self.tracefile = contents.tracefile

    def split_memory(self):
        '''
            apply the memory split between the two processes.
            
            returns:
                two page tables with split frames.
        '''
        if (int(self.memory_split[0]) < 0 or int(self.memory_split[2]) < 0 ):
            return -1
        ratio1 = int(self.memory_split[0]) / (int(self.memory_split[0])+int(self.memory_split[2]))
        ratio2 = int(self.memory_split[2]) / (int(self.memory_split[0])+int(self.memory_split[2]))
        return [page_table(ratio1*self.frames), page_table(ratio2*self.frames)]

    def parse_line(self, line):
        '''
            parses the content of a memory refrence from the trace file.
        
            args:
                a single line of the trace file.
                
            returns:
                dirty bit, address of frame, and table-idx which specifies which process is running.
        '''
        line = line.split(' ')
        dirty_bit = 0 if line[0]=='l' else 1
        frame = int(line[1], 16) >> self.offset
        table_idx = int(line[2][0])
        return dirty_bit, frame, table_idx
    
    def run_sim(self):
        '''
            runs the virtual memory simulation for a given replacment algorithm.
        '''
        if self.algorithm == 'opt': self.opt_sim()
        else: self.lru_sim()
    
    def lru_sim(self):
        '''
           performs the least recently used (LRU) simulation (counter implementaion)
        '''
        tables = self.split_memory()
        for i, line in enumerate(open(self.tracefile)):
            self.memory_accesses += 1
            dirty_bit, frame, table_idx =  self.parse_line(line)

            if frame not in tables[table_idx].entries.keys():       # miss
                self.page_faults += 1

                if tables[table_idx].isFull():                      # table full -- must evict
                    frame_to_evict = None

                    lru = sys.maxsize
                    for key in tables[table_idx].entries.keys():           # find lru
                        if tables[table_idx].entries[key][1] < lru:
                            lru = tables[table_idx].entries[key][1]
                            frame_to_evict = key
                    
                    if tables[table_idx].entries[frame_to_evict][0] == 1:   # check if disk write
                        self.disk_writes += 1

                    tables[table_idx].entries.pop(frame_to_evict)           # remove entry

                tables[table_idx].entries[frame] = [dirty_bit, i]

            else:                                                           # hit
                if tables[table_idx].entries[frame][0] == 1 or dirty_bit == 1:
                    tables[table_idx].entries[frame] = [1, i]
                else:
                    tables[table_idx].entries[frame] = [0, i]

    def opt_sim(self):
        '''
           performs the optimal page replacement algorithm simulation(OPT).
        '''
        tables = self.split_memory()
        for i, line in enumerate(open(self.tracefile)):             # first pass -- load frq map
            dirty_bit, frame, table_idx =  self.parse_line(line)

            if frame not in tables[table_idx].freq:
                tables[table_idx].freq[frame] = [i]
            else:
                tables[table_idx].freq[frame].append(i)

        # reverse frq list to optimize runtime complexity
        #   -- take advantage of pop()
        #   -- O(1) if last entry otherwise O(n)
        for table in tables:
            for key in table.freq:
                table.freq[key] = table.freq[key][::-1]
            
        for i, line in enumerate(open(self.tracefile)):                 # second pass -- simulation
            self.memory_accesses += 1
            dirty_bit, frame, table_idx =  self.parse_line(line)

            if frame not in tables[table_idx].entries.keys():           # miss 
                self.page_faults += 1

                if tables[table_idx].isFull():                          # table full -- must evict
                    frame_to_evict = None

                    nxt_access, lru = -1, sys.maxsize
                    for key in tables[table_idx].entries.keys():
                        
                        # compute lru when at least one page is not accessed again 
                        if len(tables[table_idx].freq[key])==0 and tables[table_idx].entries[key][1] < lru:
                            lru = tables[table_idx].entries[key][1]
                            frame_to_evict = key

                        # find optimal -- page accessed furthest into future
                        elif lru == sys.maxsize:
                            if tables[table_idx].freq[key][-1] > nxt_access:
                                nxt_access = tables[table_idx].freq[key][-1]
                                frame_to_evict = key
                    
                    if tables[table_idx].entries[frame_to_evict][0] == 1:   # check if disk write
                        self.disk_writes += 1

                    tables[table_idx].entries.pop(frame_to_evict)           # remove entry

                tables[table_idx].freq[frame].pop()
                tables[table_idx].entries[frame] = [dirty_bit, i]

            else:                                                           # hit
                tables[table_idx].freq[frame].pop()
                if tables[table_idx].entries[frame][0] == 1 or dirty_bit == 1:
                    tables[table_idx].entries[frame] = [1, i]
                else:
                    tables[table_idx].entries[frame] = [0, i]


    def print_results(self):
        '''
            prints relevant information and results from the simulation 
        '''
        print("Algorithm: " + str(self.algorithm.upper()))
        print("Number of frames: " + str(self.frames))
        print("Page size: " + str(self.page_size) + " KB")
        print("Total memory accesses: " + str(self.memory_accesses))
        print("Total page faults: " + str(self.page_faults))
        print("Total writes to disk: " + str(self.disk_writes))

class page_table():
    '''
        page table for a single process. 
    '''
    def __init__(self, frames):
        self.frames = frames
        self.entries = {}   # {page number in table: [dirty bit, line number]}
        self.freq = {}      # for optimal. {page number: [line numbers page accessed]}
    
    def isFull(self):
        '''
            checks if the page table is full
            
            returns:
                true if the page table is full
        '''
        if len(self.entries) == self.frames: return True
        return False

if __name__ == "__main__":
    vm_sim = virtual_memory_sim()
    vm_sim.parse_args()
    # cProfile.run('vm_sim.run_sim()')
    vm_sim.run_sim()
    vm_sim.print_results()
