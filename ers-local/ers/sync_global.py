#!/usr/bin/python

import couchdbkit
import couchdbkit.changes
import rdflib
import json
import time
import os.path
import requests

from threading import Thread
from time import sleep 
from collections import defaultdict
from models import ModelS, ModelT
from ers import ERSReadWrite
from couchdbkit.changes import ChangesStream
from string import Template
                                                        
# Document model is used to store data in CouchDB. The API is independent from the choice of model.
DEFAULT_MODEL = ModelS()
# Maximum this number of changes are retrieved once. It can be an issue if the DB has never been synchronized
LIMIT_MAXSEQ_PER_OP = 1000
# A timeout of this amount of secs is run inbetween two consecutive synchronizations.
SYNC_PERIOD_SEC=5
# HTTP address of the global server 
GLOBAL_SERVER_HOST = "127.0.0.1"
GLOBAL_SERVER_PORT = 8080
# The RESTful endpoint for handling the last synchronized sequence
GLOBAL_SERVER_HTTP_SEQ = "/ers/last_sync_seq"
# RESTful endpoint for uploading a file containing document changes
GLOBAL_SERVER_HTTP_BULKRUN = "/ers/bulkrun"
# The filename used to dump the changes
OUTPUT_FILENAME = Template("changes_$graph.log")


class GraphSynch(Thread):
    """ Creates a synch thread for a given graph using _changes feed """
    def __init__(self, ERSReadWrite, name, graph): 
        Thread.__init__(self)
        self.ers = ERSReadWrite
        self.name = name
        self.graph = graph
        self.finished = False
        if not self.ers.db.doc_exist(self.filter_by_graph_doc()['_id']):
            self.ers.db.save_doc(self.filter_by_graph_doc())
        self.output_filename = OUTPUT_FILENAME.substitute(graph = self.graph)
        

    """ Ask global server what was the last synchronized sequence number for this graph.  """
    def get_previous_seq_num(self):
        r = requests.get("http://"+GLOBAL_SERVER_HOST+":"+str(GLOBAL_SERVER_PORT)+GLOBAL_SERVER_HTTP_SEQ+
                            "?g=<"+self.graph+">")
        if r.status_code == 200:
            return r.text 
        else: 
            print 'Error getting the previous sequence number' 
            print r.status_code, r.reason
            return -1

    """ Update the global last synchronized sequence number for this graph """
    def set_new_seq_num(self, new_seq):
        r = requests.post("http://"+GLOBAL_SERVER_HOST+":"+str(GLOBAL_SERVER_PORT)+GLOBAL_SERVER_HTTP_SEQ,
                            data={"g" : "<"+self.graph+">", "seq" : new_seq})
        if r.status_code == 200: 
            return True
        else: 
            print r.status_code, r.reason
            return False
        

    """ Defines the filter document by graph. One DB stores multiple graphs. """
    def filter_by_graph_doc(self):
        return  {
            "_id": "_design/filter",
            "filters": {
                    "by_graph": "function(doc, req) { if(doc._id.substring(0, req.query.g.length) === req.query.g)  return true;  else return false; }"
                    }
               }


    def dump_changes_to_file(self, prev_seq, stream): 
        if os.path.exists(self.output_filename): 
            os.remove(self.output_filename)
        o_file = open(self.output_filename, "w")

        last_seq_n = prev_seq
        for c in stream:
            last_seq_n = c['seq']
            # Has the document been deleted? 
            if 'deleted' in c and c['deleted'] == True: 
                doc_id = "<"+c['id'][len(self.graph)+1:]+">"
                o_file.write(doc_id + " <NULL> <NULL> \"4\" . \n")
            else: 
                doc_id = "<"+c['doc']['_id'][len(self.graph)+1:]+">"
                add_delete = False
                for param in c['doc'].keys():  
                    if param == '_rev' or param == '_id': 
                        continue
                    if param.startswith('http'):
                        param2 = "<" + param + ">"
                    else:
                        param2 = "\"" + param + "\""
                    if not add_delete: 
                        o_file.write(doc_id + " <NULL> <NULL> \"4\" . \n")        
                        add_delete = True
        
                    if c['doc'][param] == None:
                        value = ""
                        o_file.write(doc_id + " " + param2 + " " + value + " \"1\" . \n")
                    else:
                        for list_value in c['doc'][param]:
                            if list_value.startswith('http'):
                                value = "<" + list_value + ">" 
                            else:
                                value = "\"" + list_value + "\""
                            o_file.write(doc_id + " " + param2 + " " + value + " \"1\" . \n")
        o_file.close()
        return last_seq_n


    def set_finished(self): 
        self.finished = True


    def run(self): 
        while True: 
            if self.finished:
                break
            time.sleep(SYNC_PERIOD_SEC)
            # get previous successfully synchronized sequence from global server 
            prev_seq_n = int(self.get_previous_seq_num())
            if prev_seq_n == -1: 
                continue

            #print "Previous sequence: " + str(prev_seq_n)
            stream = ChangesStream(self.ers.db, feed="normal", since=prev_seq_n, 
                        include_docs=True, limit=LIMIT_MAXSEQ_PER_OP, filter="filter/by_graph", g=self.graph)
            # dump to file the changes and post it to global server is not empty
            last_seq_n = self.dump_changes_to_file(prev_seq_n, stream) 
            # are there entities to be synchronized?
            if last_seq_n == prev_seq_n: 
                print 'Nothing new ...'
                continue

            """ Now upload the changes file to global server. """
            r = requests.post("http://"+GLOBAL_SERVER_HOST+":"+str(GLOBAL_SERVER_PORT)
                    +GLOBAL_SERVER_HTTP_BULKRUN, files={self.output_filename: open(self.output_filename, 'rb')},
                    data={"g" : "<"+self.graph+">"})
            if r.status_code == 200: 
                # it means that this step of synchronization is working 
                self.set_new_seq_num(last_seq_n)
                print 'Last synchronization sequence number is ' + str(last_seq_n)
            

class SynchronizationManager(object):
    def __init__(self, ERSReadWrite):
        self.active_repl = dict() 
        self.ers = ERSReadWrite

    def get_thread_name(self, graph): 
        return 'synch_'+graph

    def exists_synch_thread(self, graph): 
        return self.get_thread_name(graph) in self.active_repl

    def start_synch(self, graph):
        if self.exists_synch_thread(graph):
            print 'Another thread that synchronize graph ' + graph + ' already runs!'
        new_synch = GraphSynch(self.ers, self.get_thread_name(graph), graph)
        new_synch.start()
        # add the new thread into the dictionary
        self.active_repl[self.get_thread_name(graph)] = new_synch
        
       
    def stop_synch(self, graph):
        if self.get_thread_name(graph) in self.active_repl: 
            thread = self.active_repl[self.get_thread_name(graph)]
            if thread.isAlive(): 
               thread.set_finished() 
        else:
            print 'Synchronization thread for graph ' + graph + ' does not exist.'

    

def test():
    synch_manager = SynchronizationManager(ERSReadWrite(server_url=r'http://127.0.0.1:5984/', dbname='ers_models', model=DEFAULT_MODEL))
    graph_to_synch = 'test'
    synch_manager.start_synch(graph_to_synch)  
    time.sleep(100)
    synch_manager.stop_synch(graph_to_synch)

if __name__ == '__main__':
    test()

