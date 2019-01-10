#!/Library/Frameworks/Python.framework/Versions/3.6/bin/python3

import requests
import xmltodict
import sqlite3
import os
import sys
import time

from datetime import datetime as dt
from collections import OrderedDict

class dataProcessor:
    """
    etl for the metadata
    """
    def __init__(self, entry):
        self.entry = entry
        self.date_published = None
        self.pdf_link = None
        self.authors = None
        self.title = None
        self.summary = None
        self.year_published = None
        self.month_published = None
        self.day_published = None
    
    def get_pdf_link(self):
        """
        Horrible hacky way to make sure only get pdf links
        although there are some pdf links that are available for pdfs that do not exist
        """
        links = self.entry['link']
        numb_links = len(links)
        pdf_link = None
        
        for idx in range(numb_links):
            if '@type' not in links[idx].keys():
                pass
            elif links[idx]['@type'] == 'application/pdf':
                pdf_link = links[idx]['@href']
        
        return pdf_link
    
    def get_authors(self):
        """
        author can be a list (>1), or a single OrderedDict (==1)
        so this inelegant solution is necessary
        """
        numb_authors = len(self.entry['author'])
        if numb_authors == 1:
            authors = self.entry['author']['name']
        elif numb_authors > 1:
            authors = [self.entry['author'][idx]['name'] for idx in range(0, numb_authors)]
            authors = "_".join(authors)
        
        return authors
    
    def datetime_conversion(self):
        """
        Convert <str> 2018-01-01T16:55:55Z to <str> 2018-01-01.
        """
        string_to_time = time.strptime(self.entry['published'],'%Y-%m-%dT%H:%M:%SZ')
        time_to_string = time.strftime('%Y-%m-%d',string_to_time)
        
        return time_to_string
    
    def create_pdf_filename(self):
        if self.pdf_link is not None:
            return self.pdf_link.split('/')[-1] + ".pdf"
        else:
            return None
    
    def extract(self):
        self.authors = self.get_authors()
        self.pdf_link = self.get_pdf_link()
        self.date_published = self.datetime_conversion()
        self.year_published, self.month_published, self.day_published = self.date_published.split("-")
        self.title = self.entry['title']
        self.summary = self.entry['summary']
        self.pdf_filename = self.create_pdf_filename()
    
    def load(self):
        return (self.date_published\
                , self.year_published\
                , self.month_published\
                , self.day_published\
                , self.pdf_link\
                , self.pdf_filename\
                , self.title\
                , self.summary\
                , self.authors\
            )

class DB:
    """
    initialise sqlite3 db in dl_dir and insert metadata about paper into tables for later analysis
    """
    def __init__(self, dl_dir):
        """
        Initialise a metadata database using sqlite3
        Create table with summary, title information etc. for future queries/paper research.
        """
        self.db_conn = sqlite3.connect(dl_dir + "metadata.db")
        self.cursor = self.db_conn.cursor()
        self.__create_table()
        self.__commit()
    
    def __create_table(self):
        self.cursor.execute(
                    """CREATE TABLE IF NOT EXISTS metadata 
                    (
                        date_published text
                        , year_published text
                        , month_published text
                        , day_published text
                        , pdf_link text
                        , pdf_filename text
                        , title text
                        , summary text
                        , authors text
                    )
                    """
                    )
    
    def insert_metadata(self, t):
        """
        Insert data into the specified sqlite3 database
        """
        try:
            self.cursor.execute("""INSERT INTO metadata VALUES (?,?,?,?,?,?,?,?,?)""", t)
            self.__commit()
        except Exception as e:
            print("<db_insert_metadata> encountered an exception:" + e)
        return True
    
    def __commit(self):
        self.db_conn.commit()
    
    def close(self):
        self.db_conn.close()

class pdfWriter:
    """
    get the pdf file content from arxiv then write it safely to the desired dir
    """
    def __init__(self, link, p_date, fname, dl_dir):
        self.data = None
        self.fname = fname
        self.date_dir = dl_dir + p_date + "/"
        self.path = self.date_dir + fname
        self.url = link
        self.existing_files = None
    
    def create_paths(self):
        if not os.path.exists(self.date_dir):
            os.mkdir(self.date_dir)
    
    def get_existing_files(self):
        self.existing_files = os.listdir(self.date_dir)
    
    def write_binary_content(self):
        """
        Safely write binary file content.
        """
        if ".pdf" not in self.path:
            self.path = self.path + ".pdf"
        try:
            with open(self.path, 'wb+') as f:
                f.write(self.data)
        except Exception as e:
            print("<write_pdf> encountered an error: {err}".format(err=e))
        else:
            return True
    
    def get_pdf(self):
        self.create_paths()
        self.get_existing_files()
        logs = Logging(self.fname, self.date_dir)
        if self.fname is not None and self.fname not in self.existing_files:
            r = get_request(self.url)
            self.data = r.content
            self.write_binary_content()
            logs.success()
            time.sleep(3)
        elif self.fname is None or self.fname in self.existing_files:
            logs.skipped()
        else:
            logs.other()
    
class Logging:
    """
    Logger class that just prints to stdout.
    """
    def __init__(self, pdf_id, data_dir):
        self.pdf_id = pdf_id
        self.data_dir = data_dir
    
    def success(self):
        output_string = "Saved {} to {}".format(self.pdf_id, self.data_dir)
        print(dt.now(), output_string)
    
    def skipped(self):
        output_string = "Skipped {} - pdf is either <None> or exists in {}".format(self.pdf_id, self.data_dir)
        print(dt.now(), output_string)
    
    def other(self):
        print("Did not save pdf for an uknown reason.")

def get_request(url):
    """
    requests.get() with personalised error handling.
    """
    try:
        r = requests.get(url)
    except Exception as e:
        err = "<get_requests> encountered an exception for: {} : {}".format(url,e)
        print(dt.now(), err)
        sys.exit(1)
    else:
        if r.status_code != 200:
            err = "<get_requests> called the api, but got a non-200 status code for: {}".format(url)
            raise Exception(dt.now(), err)
            return None
        else:
            return r

def main(n=100, dl_dir = "/Users/Mike/data/data-files/auto-arxiv/CS_ML/"):
    """
    main runtime script
    """
    category_searches = "search_query=cat:cs.CR+AND+%28cat:stat.ML+OR+cat:cs.LG+OR+cat:cs.CV+OR+cat:cs.AI%29"
    full_query = "{sq}&start={s}&max_results={n}&sortBy={sd}&sortOrder={so}".format(
                                            sq=category_searches
                                            , s=0
                                            , n=n
                                            , sd='submittedDate'
                                            , so='descending'
                                        )
    arxiv_api_url = "http://export.arxiv.org/api/query?{query_string}".format(query_string=full_query)
    search_data = xmltodict.parse(get_request(arxiv_api_url).text)
    meta_db = DB(dl_dir)
    
    for entry in search_data['feed']['entry']:
        
        entryETL = dataProcessor(entry)
        entryETL.extract()
        tags = entryETL.load()
        
        meta_db.insert_metadata(tags)
        
        date = tags[0]
        link, fname = tags[4:6]
        
        pdf_getter = pdfWriter(link, date, fname, dl_dir)
        pdf_getter.get_pdf()
    
    meta_db.close()

if __name__ == '__main__':
    main()