from dataclasses import dataclass
from json import load


@dataclass(init=False)
class ApiKeys:
    here: str = ''

    def __init__(self, file_name: str):
        # read json file and initialize the api keys
        data = load(open(file_name, 'r'))
        if 'here' in data:
            self.here = data['here']


if __name__ == '__main__':
    print(ApiKeys('../config/api_keys.json'))
