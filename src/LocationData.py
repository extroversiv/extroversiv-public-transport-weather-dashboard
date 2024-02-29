from abc import ABC, abstractmethod


class LocationData(ABC):

    def __init__(self):
        self._locations = {}  # internal storage of station information

    @abstractmethod
    def find_locations(self, name, number):
        pass

    @abstractmethod
    def get_data(self, name):
        pass

    def update_locations(self, names):
        # delete extra stations
        superfluous_locations = set(self._locations.keys()) - set(names)
        for name in superfluous_locations:
            self._locations.pop(name)

        # get missing stations
        missing_locations = set(names) - set(self._locations.keys())
        for name in missing_locations:
            self.find_locations(name=name, number=1)
