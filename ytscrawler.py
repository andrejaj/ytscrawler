import requests
from bs4 import BeautifulSoup
import urllib.parse
import time
import ssl
import re
import json
import logging

#genres = ['Action', 'Adventure', 'Animation', 'Biography', 'Comedy', 'Crime',
#          'Documentary', 'Drama', 'Family', 'Fantasy', 'Film Noir', 'History',
#          'Horror', 'Music', 'Musical', 'Mystery', 'Romance', 'Sci-Fi',
#          'Short', 'Sport', 'Superhero', 'Thriller', 'War', 'Western']

class CrawlBase:
    def __init__(self, url):
        self.base_url = url
        self.http_options = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
            "timeout": "20",
            "verify": "False"
        }

    # def encode_data(self, content):
    #     if content is not None:
    #         return content.encode("ISO-8859-1").decode("utf-8", "ignore")
    #     else:
    #         return None
    def normalized_url(self, url):
        return urllib.parse.urljoin(self.base_url, url)
    def download(self, url):
        return requests.get(self.normalized_url(url), headers=self.http_options).text
    def page(self, url):

        data = []
        try:
            soup = BeautifulSoup(self.download(url), "html.parser")
            script  = soup.find_all("script", {"type":"application/ld+json"})[1]
            data = json.loads(script.text)['itemListElement']
        except Exception as error:
            logger.error(f'processing page {url}', error)

        return data
    

    def page_details(self, url):

        data = {}

        try:
            page = requests.get(url)
            soup = BeautifulSoup(page.content, 'html.parser')
        
            data['imdb_url'] = soup.find('a', title='IMDb Rating').get('href')

            urls = set()
            for link in soup.findAll('a', href=re.compile("magnet")):
                urls.add(link.get('href'))
       
            items = list(urls)
            try:
                data["torrent_720"] = items[0]
            except:
                data["torrent_720"] = None
            try:
                data["torrent_1080"] = items[1]
            except:
                data["torrent_1080"] = None
        except Exception as error:
            logger.error(f'processing page details {url}', error)
        return data
    
    def page_imdb_details(self, url):
        
        movie_data = {}

        try:
            data = {}
            soup = BeautifulSoup(self.download(url), 'html.parser')
            language = soup.find('a', href=re.compile("primary_language")).text
            releaseDate = soup.find('a', href=re.compile("releaseinfo")).text
            countryOrigin = soup.find('a', href=re.compile("country_of_origin")).text
        
        
            script  = soup.find_all("script", {"type":"application/ld+json"})[0]
            data = json.loads(script.text)

            movie_data = {}
            movie_data['description'] = data['description']
            movie_data['genre'] = data['genre']
            movie_data['imdb_rating'] = data['aggregateRating']['ratingValue']
            movie_data['releasedate'] = releaseDate
            movie_data['language'] = language
            movie_data['countryOrigin'] = countryOrigin
        except Exception as error:
          movie_data = None
          logger.error(f'processing imdb data {url}', error)  
        return movie_data

class Yts(CrawlBase):
    def __init__(self, url, yts_options={}):
        super().__init__(url)
        self.movies = {}
        self.options = {}
        self.options["from"] = yts_options.get("from", 1)
        self.options["to"] = yts_options.get("to", 299)
        self.options["imdb_rating_gt"] = yts_options.get("imdb_rating_gt")
        self.options["rt_critic_rating_gt"] = yts_options.get("rt_critic_rating_gt")
        self.options["year_gt"] = yts_options.get("year_gt")
        self.options["exclude_genres"] = yts_options.get("exclude_genres", ["Documentary", "Romance", "Talk-Show", "Reality-TV", "News", "Musical", "Music", "Animation", "Western", "Short", "Sport"])
        self.options["include_languages"] = yts_options.get("include_languages", ["English", "Spanish", "Italian", "Portuguese"])
    def parse(self):
        for page_number in range(self.options["from"], self.options["to"] + 1):
            url = f"{self.base_url}?page={page_number}"
            logger.info(url)   
            print(url)
            data = self.page(url)

            for item in data:
                skip_movie = False
                movie = {}
                movie['title'] = item['item']['name']
                movie['url'] = item['item']['url']
                movie['image'] = item['item']['image']
                
                rg = re.compile(r'[^a-z](\d{4})[^a-z]', re.IGNORECASE)
                match = rg.findall(movie['title'])

                #check release year from yts
                if not skip_movie and self.options["year_gt"] and int(match[0]) < self.options["year_gt"]:
                    skip_movie = True
                
                if not skip_movie:
                  movie_data = self.page_details(movie['url'])
                  if not movie_data:
                    logger.error(f"no magnetic link {movie['url']}") 
                    continue
                  
                  movie["torrent_720"] = movie_data['torrent_720']
                  movie["torrent_1080"] = movie_data['torrent_1080']

                  imdb_data = self.page_imdb_details(movie_data['imdb_url'])
                  if not imdb_data:
                    logger.error(f"no imdb data {movie_data['imdb_url']}") 
                    continue
                  
                  movie['description'] = imdb_data['description']
                  movie['genres'] = imdb_data['genre']
                  movie['imdb_rating'] = imdb_data['imdb_rating']
                  movie['year'] = imdb_data['releasedate']
                  movie['language'] = imdb_data['language']
                  movie['countryOrigin'] = imdb_data['countryOrigin']
                  
                #imdb rating  
                if not skip_movie and self.options["imdb_rating_gt"] and movie["imdb_rating"] < float(self.options["imdb_rating_gt"]):
                    skip_movie = True

                #imdb genres     
                if not skip_movie and self.options["exclude_genres"] and isinstance(self.options["exclude_genres"], list):
                    for genre in movie["genres"]:
                        if genre in self.options["exclude_genres"]:
                            skip_movie = True
                            break

                #imdb year
                # if not skip_movie and self.options["year_gt"] and int(movie["year"]) < int(self.options["year_gt"]):
                #     skip_movie = True

                #imdb language
                if not skip_movie and self.options["include_languages"]:
                    if movie['language'] not in self.options["include_languages"]:
                        skip_movie = True
                        break
                    
                if not skip_movie:
                    self.movies[movie["title"]] = movie
                    logger.info(movie["title"])  
                    print(movie["title"])
        return
  
    def get_movies(self):
        return self.movies


logging.basicConfig(filename='error.log', level=logging.ERROR, 
                    format='%(asctime)s %(levelname)s %(name)s %(message)s')
logger=logging.getLogger(__name__)

years = [2020] #2020, 2021, 2022, 2023
for year in years:
    yts = Yts(f"https://yts.rs/browse-movies/{year}/all/all/5/latest", {"from": 58 ,"to":150, "imdb_rating_gt": 5, "year_gt": year}) #"from":27,
    yts.parse()

    movies = yts.get_movies()

    # output 
    with open(f"Movies_{year}.json", 'wt') as f:
        json.dump(movies, f)  
    # Closing file
    f.close()