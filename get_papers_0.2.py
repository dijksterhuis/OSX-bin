#!/usr/local/bin/python3.6

import os
from requests import get

def get_urls(out_top_dir, in_dir):
    filenames = [ filename for filename in os.listdir(in_dir) if '.txt' in filename ]
    for filename in filenames:
        with open(in_dir + filename,'r') as f: 
            urls = [ i.rstrip('\r\n') for i in f.readlines() if '.pdf' in i[-10:] ]
        if len(urls) == 0:
            pass
        else: 
            results = [result for result in save_pdf_generator(out_top_dir, filename, urls)]
            print(str(results.count(True)) + " papers saved on disk, there were a total of " + str(len(results)))

def save_pdf_generator(out_top_dir, filename, urls):
    for url in urls:
        out_name = url.split('/')[-1:][0]
        out_dir = out_top_dir + filename.rstrip('.txt')
        out_path = out_dir + "/" + out_name
        if os.path.exists(out_dir) is False: os.mkdir(out_dir)
        if os.path.exists(out_path) is False: 
            print('Saving: ' + url + ' to: ' + out_path)
            pdf = get(url)
            try:
                with open(out_path, 'wb') as f: f.write(pdf.content)
                yield True
            except:
                yield False
        else:
            yield True

def main():
    in_dir = '/Users/Mike/Desktop/sites/'
    out_top_dir = '/Users/Mike/data/local-jobs/paper-getter/pdfs/'
    get_urls(out_top_dir, in_dir)

if __name__ == '__main__':
    main()
