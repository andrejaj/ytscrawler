import requests
from bs4 import BeautifulSoup
import urllib.parse
import time
import ssl
import re
import json

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
        self.countryLanguage = { "Spain" : "Spanish", "Italy" : "Italian", "USA" : "English", "Brazil" : "Portuguese", "Portugal" : "Portuguese", "England" : "English"}
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
            print("An exception occurred:", error) 

        return data
    

    def page_details(self, url):

        data = {}
        page = requests.get(url)
        soup = BeautifulSoup(page.content, 'html.parser')
        
        data['imdb_url'] = soup.find('a', title='IMDb Rating').get('href')

        urls = set()
        for link in soup.findAll('a', href=re.compile("magnet")):
            urls.add(link.get('href'))
       
        items = list(urls)
        data["torrent_720"] = items[0]
        data["torrent_1080"] = items[1]

        return data
    
    def page_imdb_details(self, url):
        data = {}
        soup = BeautifulSoup(self.download(url), 'html.parser')

        try:
            language = soup.find('a', href=re.compile("primary_language")).text
        except:
            language = None
            print('error in processing language: ' + url)
        releaseDate = soup.find('a', href=re.compile("releaseinfo")).text
        try:
            countryOrigin = soup.find('a', href=re.compile("country_of_origin")).text
        except:
            countryOrigin = None
            print('error in processing country of origin: ' + url)

        #note: here if it fails for langiage country of origin can be taken
        try:
            if language is None and not countryOrigin is None:
                language = self.countryLanguage[countryOrigin]
        except:
            print('error in mapping country to language: ' + url)
        
        script  = soup.find_all("script", {"type":"application/ld+json"})[0]
        data = json.loads(script.text)

        movie_data = {}
        movie_data['description'] = data['description']
        movie_data['genre'] = data['genre']
        movie_data['imdb_rating'] = data['aggregateRating']['ratingValue']
        movie_data['releasedate'] = releaseDate
        movie_data['language'] = language
        movie_data['countryOrigin'] = countryOrigin
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
            print(url)
            data = self.page(url)

            for item in data:
                skip_movie = False
                movie = {}
                movie['title'] = item['item']['name']
                movie['url'] = item['item']['url']
                movie['image'] = item['item']['image']
                print(movie)

                rg = re.compile(r'[^a-z](\d{4})[^a-z]', re.IGNORECASE)
                match = rg.findall(movie['title'])

                #check release year from yts
                if not skip_movie and self.options["year_gt"] and int(match[0]) < self.options["year_gt"]:
                    skip_movie = True
                
                if not skip_movie:
                  movie_data = self.page_details(movie['url'])
                  imdb_data = self.page_imdb_details(movie_data['imdb_url'])
                  movie["torrent_720"] = movie_data['torrent_720']
                  movie["torrent_1080"] = movie_data['torrent_1080']

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
                if not skip_movie and self.options["year_gt"] and int(movie["year"]) < int(self.options["year_gt"]):
                    skip_movie = True

                #imdb language
                if not skip_movie and self.options["include_languages"]: # and isinstance(self.options["include_genres"], list):
                    if movie['language'] not in self.options["include_languages"]:
                        skip_movie = True
                        break
                    
                if not skip_movie:
                    self.movies[movie["title"]] = movie
        return
  
    def get_movies(self):
        return self.movies

yts = Yts("https://yts.rs/browse-movies", { "imdb_rating_gt": 5, "year_gt": 2023}) #"to" : 2,
yts.parse()

movies = yts.get_movies()
#print(movies)

# output 
with open("Movies.json", 'wt') as f:
    json.dump(movies, f)  
# Closing file
f.close()