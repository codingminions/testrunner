import argparse
import json
import os
import sys
import random
import datetime
import logging
import traceback

from couchbase.cluster import Cluster
from couchbase.cluster import PasswordAuthenticator
from couchbase.exceptions import NotFoundError
from couchbase.bucket import Bucket

from ValueGenerator import ValueGenerator
import constants


# Example usage: python main.py -ip 192.168.56.111 -u Administrator -p password -b default -n 5

class JSONDoc(object):
    def __init__(self, server, username, password, bucket, startseqnum, randkey, encoding, num_docs, template):
        self.json_objs_dict = {}
        self.template_file = template
        self.encoding = encoding
        self.num_docs = num_docs
        self.startseqnum = startseqnum
        self.randkey = randkey
        logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
        local = False
        if not server or len(server) < 2:
            logging.info("No valid server provided. Generating docs locally in ./output dir")
            local = True
        else:
            self.server = server
            self.username = username
            self.password = password
            self.bucket = bucket
        if local:
            self.printDoc()
        else:
            self.uploadDoc()

    def uploadDoc(self):
        # connect to cb cluster
        try:
            connection = "couchbase://" + self.server
            cluster = Cluster(connection)
            authenticator = PasswordAuthenticator(self.username, self.password)
            cluster.authenticate(authenticator)
            cb = cluster.open_bucket(self.bucket)
        except Exception as e:
            logging.error("Connection error\n" + traceback.format_exc())
        ttls = [0, 60, 120, 180, 240, 300, 360, 3600, 7200]
        for i in range(self.startseqnum, self.startseqnum + self.num_docs):
            logging.info("generating doc: " + str(i))
            self.createContent()
            dockey = "edgyjson-" + str(i) + "-" + str(datetime.datetime.now())[:19]
            try:
                cb.upsert(str(dockey), self.json_objs_dict, ttl=random.choice(ttls))
                logging.info("upsert: " + dockey)
            except Exception as e:
                logging.error("Upload error\n" + traceback.format_exc())

    def printDoc(self):
        for i in range(self.startseqnum, self.startseqnum + self.num_docs):
            logging.info("generating doc: " + str(i))
            self.createContent()
            try:
                current_dir = os.path.dirname(__file__)
                dockey = "edgyjson:" + str(i) + ":" + str(datetime.datetime.now())[:19] + ".json"
                output = os.path.join(current_dir, "output/", dockey)
                with open(output, 'w') as f:
                    f.write(json.dumps(self.json_objs_dict, indent=3).encode(self.encoding, "ignore"))
                logging.info("print: " + dockey)
            except Exception as e:
                logging.error("Print error\n" + traceback.format_exc())

    def createContent(self):
        try:
            current_dir = os.path.dirname(__file__)
            template = open(os.path.join(current_dir, "templates/", self.template_file))
            content = json.load(template)
            template.close()
        except IOError:
            logging.error("Unable to find template file , data not loaded!")

        valuegen = ValueGenerator()
        for key, value in content.items():
            if key in constants.generator_methods.keys():
                if len(value) > 1:
                    argsdict = self.parseargs(value)
                else:
                    argsdict = {}
                val = getattr(valuegen, constants.generator_methods[key])(**argsdict)
                if self.randkey:
                    func_list = [func for func in dir(valuegen) if
                                 callable(getattr(valuegen, func)) and not func.startswith("__")]
                    key = getattr(globals()['ValueGenerator'](), random.choice(func_list))()
                    # Discard rand keys that are lists or dicts
                    while isinstance(key,list) or isinstance(key, dict):
                        key = getattr(globals()['ValueGenerator'](), random.choice(func_list))()
            self.json_objs_dict[key] = val

    def parseargs(self, argsstr):
        argsindex = argsstr.split(',')
        argsdict = dict()
        for item in argsindex:
            # Separate the arg name and value
            argname, argvalue = item.split('=')
            # Add it to the dictionary
            argsdict.update({argname: argvalue})
        return argsdict


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--server', '-ip',
                        help='IP address of cb server to upload docs to. If not provided, docs will be generated locally at ./output dir',
                        type=str)
    parser.add_argument('--user', '-u', help='Server username', type=str)
    parser.add_argument('--password', '-p', help='Server password', type=str)
    parser.add_argument('--bucket', '-b', help='Bucket name', type=str)
    parser.add_argument('--startseqnum', '-s', help="Starting document ID prefix", type=int, default=1)
    parser.add_argument('--randkey', '-rk', help="Randomize keys", type=bool, default=False)
    parser.add_argument('--encoding', '-e', help="JSON Encoding format : utf-8, utf-16, utf-32", type=str,
                        default="utf-8")
    parser.add_argument('--numdocs', '-n', help="Number of documents to generate", type=int, default=1)
    parser.add_argument('--template', '-t', help="JSON Template File. Should be placed in ./templates dir", type=str,
                        default="mix.json")
    args = parser.parse_args()
    if args.server and (args.user is None or args.password is None or args.bucket is None):
        logging.error("username, password and bucket name are required")
        sys.exit(0)
    JSONDoc(args.server, args.user, args.password, args.bucket, args.startseqnum, args.randkey, args.encoding, args.numdocs,
            args.template)
