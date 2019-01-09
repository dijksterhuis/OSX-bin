#!/Library/Frameworks/Python.framework/Versions/3.6/bin/python3

import requests
import xmltodict
import os
import time
import sqlite3

from datetime import datetime as dt
from collections import OrderedDict

NUMB_RESULTS = 1000

SEARCH_QUERY_STRING = "search_query=cat:cs.CR+AND+%28cat:stat.ML+OR+cat:cs.LG%29"
QUERY_STRING = "{sq}&start={s}&max_results={n}&sortBy={sb}&sortOrder={so}".format(
                                        sq=SEARCH_QUERY_STRING,
                                        s=0,
                                        n=NUMB_RESULTS,
                                        sb='submittedDate',
                                        so='descending'
                                    )
ARXIV_API_URL = "http://export.arxiv.org/api/query?{query_string}".format(query_string=QUERY_STRING)

DOWNLOAD_DIR = "/Users/Mike/data/data-files/auto-arxiv/CS_ML/"

class ETL:
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

def get_request(url):
    """
    requests.get() with personalised error handling.
    """
    try:
        r=requests.get(url)
    except Exception as e:
        print("<get_requests> encountered an exception for: {api_url} : {err}".format(api_url=url,err=e))
    if r.status_code != 200:
        raise Exception("<get_requests> called the api, but got a non-200 status code for: {api_url}".format(api_url=url))
    else: return r

def parse_data(xml_data, parser = xmltodict.parse):
    """
    Parse xml data via the defined parser - default parser is xmltodict
    """
    parsed_data = parser(xml_data)
    return parsed_data

def generate_data_links(parsed_data):
    """
    Generator function to extract & transform necessary data from <dict>/<OrderedDict>
    """
    if not isinstance(parsed_data, OrderedDict) or not isinstance(parsed_data, OrderedDict):
        raise TypeException("<generate_data_links> only accepts <OrderedDict> or <dict> types.")
    else:
        for entry in parsed_data['feed']['entry']:
            data = ETL(entry)
            data.extract()
            yield data.load()

def write_pdf(data, path):
    """
    Safely write binary file content.
    """
    if ".pdf" not in path:
        path = path + ".pdf"
    try:
        with open(path, 'wb+') as f:
            f.write(data)
    except Exception as e:
        print("<write_pdf> encountered an error: {err}".format(err=error))
    else:
        return True


def main():
    """
    main runtime script
    """
    
    meta_db = DB(DOWNLOAD_DIR)
    search_data = parse_data(get_request(ARXIV_API_URL).text)
    
    for entry in search_data['feed']['entry']:
        
        entryETL = ETL(entry)
        entryETL.extract()
        tags = entryETL.load()
        
        date = tags[0]
        link, fname, title = tags[4:7]
        
        date_dir = DOWNLOAD_DIR + date + "/"
        if not os.path.exists(date_dir):
            os.mkdir(date_dir)
        
        existing_files = os.listdir(date_dir)
        
        if fname is not None and fname not in existing_files:
            pdf_data = get_request(link).content
            write_pdf(pdf_data, date_dir + fname)
            meta_db.insert_metadata(tags)
            print(dt.now(), "Saved {pdf_id} to {dl_dir}".format(pdf_id=fname, dl_dir=date_dir))
            time.sleep(3)
            
        elif fname is None or fname in existing_files:
            meta_db.insert_metadata(tags)
            print(dt.now(), "Skipped {pdf_id} - download is either <None> or exists in {dl_dir}".format(\
                                                            pdf_id=fname, dl_dir=date_dir)\
                                                        )
        
        else:
            print("Did not save pdf {pdf_id}/{title} for an uknown reason.".format(\
                                                        pdf_id=fname, title=title)\
                                                    )
    
    meta_db.close()

if __name__ == '__main__':
    main()