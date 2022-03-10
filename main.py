import openai
import re
import json
from time import sleep
from os.path import exists
from lxml import html
from requests import get

openai.api_key = "<YOUR-OPENAI-API-KEY>"

WIKIPEDIA_LINK = "https://en.wikipedia.org/wiki/"
TRAINING_DIRECTORY = "training_data/"

def main():

    # Fetch Wikipedia page and confirm it's valid
    page_found = False
    while page_found == False:
        title = input("Enter Wikipedia title: ").title().replace(' ', '_')
        page = get(WIKIPEDIA_LINK + title)
        if page.status_code == 200:
            page_found = True
        elif page.status_code == 404:
            print(f"{WIKIPEDIA_LINK + title} not found, please try another title")
        else:
            print(f"Something went wrong, status code: {page.status_code}")

    # File to save to later
    filename = title + '.jsonl'

    # Check if json lines file already exists. This prevents duplicate uploads to OpenAI
    if exists(f"{TRAINING_DIRECTORY + title}.jsonl") == False:
        # Clear file to be rewritten from OpenAI if it exists
        uploaded_file = list(filter(lambda x: x.filename == filename, openai.File.list()["data"]))
        if len(uploaded_file) != 0:
            openai.File.delete(uploaded_file[0].id)

        # Parse the text
        print(f"Parsing {WIKIPEDIA_LINK + title}")
        tree = html.fromstring(page.content)

        # Take all paragraphs and convert inner tags to plain text
        bad_tags = ["a", "sup", "i", "b", "span"]
        for bad_tag in bad_tags:
            tags_in_paragraphs = tree.xpath(f"//div[@class='mw-parser-output']//p//{bad_tag}")
            for tag in tags_in_paragraphs:
                tag.drop_tag()

        # Drop empty paragraphs
        paragraphs_xpath = [x for x in tree.xpath("//div[@class='mw-parser-output']//p") if x.text != None]

        # Remove citation text
        citation_pattern = r'\[\d*\]'
        paragraphs = [{'text': f"{re.sub(citation_pattern, '', x.text)}"} for x in paragraphs_xpath]

        # Write each paragraph as json line
        with open(f"{TRAINING_DIRECTORY + title}.jsonl", "w") as f:
            idx = 0
            for paragraph in paragraphs:
                if idx == len(paragraphs) - 1:
                    f.write(json.dumps(paragraph))
                else:
                    f.write(json.dumps(paragraph) + '\n')
                idx += 1

            # Upload json lines file
            openai.File.create(file=open(TRAINING_DIRECTORY + filename), purpose='answers')
            uploading = True
            uploaded_file = list(filter(lambda x: x.filename == filename, openai.File.list()["data"]))[0]

            # Wait until file has been processed by OpenAI
            while uploading == True:
                print(f"Processing {filename}: {uploaded_file.status}")
                uploaded_file = list(filter(lambda x: x.filename == filename, openai.File.list()["data"]))[0]
                if uploaded_file.status == "processed":
                    uploading = False
                else:
                    sleep(3)

    else:
        # Fetch the preexisting file from OpenAI
        print(f"{WIKIPEDIA_LINK + title} has been previously parsed")
        uploaded_file = list(filter(lambda x: x.filename == filename, openai.File.list()["data"]))[0]

    while True:
        question = input("Q: ")
        if question == "":
            return
        print(openai.Answer.create(
        search_model="davinci",
        model="davinci",
        question=question,
        file=uploaded_file.id,
        temperature=.1,
            #You may want to change this example to suit your own needs.
        examples_context="William James Murray (born September 21, 1950) is an American actor and comedian, known for his deadpan delivery. He rose to fame on The National Lampoon Radio Hour (1973–1974) before becoming a national presence on Saturday Night Live from 1977 to 1980, where he received a Primetime Emmy Award for Outstanding Writing for a Variety Series. He starred in comedy films such as Meatballs (1979), Caddyshack (1980), Stripes (1981), Tootsie (1982), Ghostbusters (1984), Scrooged (1988), Ghostbusters II (1989), What About Bob? (1991), Groundhog Day (1993), Kingpin (1996), The Man Who Knew Too Little (1997) and Osmosis Jones (2001). His only directorial credit is Quick Change (1990), which he co-directed with Howard Franklin.",
        examples=[["What is bill's full name", "William James Murray"], ["When was he born", "September 21, 1950"], ["Was bill in Meatballs?", "yes"], ["Was bill in the godfather?", "no"]],
        max_rerank=100,
        max_tokens=100,
        stop=["\n", "<|endoftext|>"]
        )["answers"][0])

if __name__ == "__main__":
    main()
