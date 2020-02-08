import copy
from collections import defaultdict
import itertools

from Region import TimeOfDay


class Search(object):

    def __init__(self, state_list, initial_cache=None):
        self.state_list = [state.copy() for state in state_list]

        # Let the states reference this search.
        for state in self.state_list:
            state.search = self

        if initial_cache:
            self._cache = initial_cache
            self.cached_spheres = [self._cache]
        else:
            root_regions = [state.world.get_region('Root') for state in self.state_list]
            # The cache is a dict with 5 values:
            #  child_regions, adult_regions: maps of Region -> tod, all the regions in that sphere
            #    values are lazily-determined tod flags (see TimeOfDay).
            #  child_queue, adult_queue: queue of Entrance, all the exits to try next sphere
            #  visited_locations: set of Locations visited in or before that sphere.
            self._cache = {
                'child_queue': list(exit for region in root_regions for exit in region.exits),
                'adult_queue': list(exit for region in root_regions for exit in region.exits),
                'visited_locations': set(),
                'child_regions': {region: TimeOfDay.NONE for region in root_regions},
                'adult_regions': {region: TimeOfDay.NONE for region in root_regions},
            }
            self.cached_spheres = [self._cache]
            self.next_sphere()


    def copy(self):
        # we only need to copy the top sphere since that's what we're starting with and we don't go back
        new_cache = {k: copy.copy(v) for k,v in self._cache.items()}
        # copy always makes a nonreversible instance
        return Search(self.state_list, initial_cache=new_cache)


    def collect_all(self, itempool):
        for item in itempool:
            self.state_list[item.world.id].collect(item)


    def collect(self, item):
        self.state_list[item.world.id].collect(item)


    @classmethod
    def max_explore(cls, state_list, itempool=None):
        p = cls(state_list)
        if itempool:
            p.collect_all(itempool)
        p.collect_locations()
        return p

    @classmethod
    def with_items(cls, state_list, itempool=None):
        p = cls(state_list)
        if itempool:
            p.collect_all(itempool)
        p.next_sphere()
        return p

    # Truncates the sphere cache based on which sphere a location is in, and
    # drops the location from the appropriate visited set.
    # Doesn't forget which sphere locations are in as an optimization, so be careful
    # to only unvisit locations in descending sphere order, or locations that
    # have been revisited in the most recent iteration.
    # Locations never visited in this Search are assumed to have been visited
    # in sphere 0, so unvisiting them will discard the entire cache.
    # Not safe to call during iteration.
    def unvisit(self, location):
        raise Exception('Unimplemented for Search. Perhaps you want RewindableSearch.')


    # Drops the item from its respective state.
    # Has no effect on cache!
    def uncollect(self, item):
        self.state_list[item.world.id].remove(item)


    # Resets the sphere cache to the first entry only.
    # Does not uncollect any items!
    # Not safe to call during iteration.
    def reset(self):
        raise Exception('Unimplemented for Search. Perhaps you want RewindableSearch.')


    # Internal to the iteration. Modifies the exit_queue, regions. 
    # Returns a queue of the exits whose access rule failed, 
    # as a cache for the exits to try on the next iteration.
    def _expand_regions(self, exit_queue, regions, age):
        failed = []
        for exit in exit_queue:
            if exit.connected_region and exit.connected_region not in regions:
                # Evaluate the access rule directly, without tod
                if exit.access_rule(self.state_list[exit.world.id], spot=exit, age=age):
                    regions[exit.connected_region] = exit.connected_region.provides_time
                    regions[exit.world.get_region('Root')] |= exit.connected_region.provides_time
                    exit_queue.extend(exit.connected_region.exits)
                else:
                    failed.append(exit)
        return failed


    def _expand_tod_regions(self, regions, goal_region, age, tod):
        # grab all the exits from the regions with the given tod in the same world as our goal.
        # we want those that go to existing regions without the tod, until we reach the goal.
        has_tod_world = lambda regtod: regtod[1] & tod and regtod[0].world == goal_region.world
        exit_queue = list(itertools.chain.from_iterable(region.exits for region, _ in filter(has_tod_world, regions.items())))
        for exit in exit_queue:
            # We don't look for new regions, just spreading the tod to our existing regions
            if exit.connected_region in regions and tod & ~regions[exit.connected_region]:
                # Evaluate the access rule directly
                if exit.access_rule(self.state_list[exit.world.id], spot=exit, age=age, tod=tod):
                    regions[exit.connected_region] |= tod
                    if exit.connected_region == goal_region:
                        return True
                    exit_queue.extend(exit.connected_region.exits)
        return False


    # Explores available exits, updating relevant entries in the cache in-place.
    # Returns the regions accessible in the new sphere as child,
    # the regions accessible as adult, and the set of visited locations.
    # These are references to the new entry in the cache, so they can be modified
    # directly.
    def next_sphere(self):

        # Use the queue to iteratively add regions to the accessed set,
        # until we are stuck or out of regions.
        self._cache.update({
            # Replace the queues (which have been modified) with just the
            # failed exits that we can retry next time.
            'adult_queue': self._expand_regions(
                self._cache['adult_queue'], self._cache['adult_regions'], 'adult'),
            'child_queue': self._expand_regions(
                self._cache['child_queue'], self._cache['child_regions'], 'child'),
        })
        return self._cache['child_regions'], self._cache['adult_regions'], self._cache['visited_locations']

    # Yields every reachable location, by iteratively deepening explored sets of
    # regions (one as child, one as adult) and invoking access rules.
    # item_locations is a list of Location objects from state_list that the caller
    # has prefiltered (eg. by whether they contain advancement items).
    #
    # Inside the loop, the caller usually wants to collect items at these
    # locations to see if the game is beatable. Collection should be done
    # using internal State (recommended to just call search.collect).
    def iter_reachable_locations(self, item_locations):
        had_reachable_locations = True
        # will loop as long as any visits were made, and at least once
        while had_reachable_locations:
            child_regions, adult_regions, visited_locations = self.next_sphere()

            # Get all locations in accessible_regions that aren't visited,
            # and check if they can be reached. Collect them.
            had_reachable_locations = False
            for loc in item_locations:
                if (loc not in visited_locations
                    # Check adult first; it's the most likely.
                    and (loc.parent_region in adult_regions
                         and loc.access_rule(self.state_list[loc.world.id], spot=loc, age='adult')
                         or (loc.parent_region in child_regions
                             and loc.access_rule(self.state_list[loc.world.id], spot=loc, age='child')))):
                    had_reachable_locations = True
                    # Mark it visited for this algorithm
                    visited_locations.add(loc)
                    yield loc


    # This collects all item locations available in the state list given that
    # the states have collected items. The purpose is that it will search for
    # all new items that become accessible with a new item set.
    def collect_locations(self, item_locations=None):
        item_locations = item_locations or self.progression_locations()
        for location in self.iter_reachable_locations(item_locations):
            # Collect the item for the state world it is for
            self.collect(location.item)

    # A shorthand way to iterate over locations without collecting items.
    def visit_locations(self, locations=None):
        locations = locations or self.progression_locations()
        for _ in self.iter_reachable_locations(locations):
            pass

    # Retrieve all item locations in the worlds that have progression items
    def progression_locations(self):
        return [location for state in self.state_list for location in state.world.get_locations() if location.item and location.item.advancement]


    # This returns True if every state is beatable. It's important to ensure
    # all states beatable since items required in one world can be in another.
    # A state is beatable if it can ever collect the Triforce.
    # If scan_for_items is True, constructs and modifies a copy of the underlying
    # state to determine beatability; otherwise, only checks that the search
    # has already acquired all the Triforces.
    #
    # The above comment was specifically for collecting the triforce. Other win 
    # conditions are possible, such as in Triforce Hunt, where only the total
    # amount of an item across all worlds matter, not specifcally who has it
    #
    # Win condition can be a string that gets mapped to a function(state_list) here
    # or just a function(state_list)
    def can_beat_game(self, scan_for_items=True):

        # This currently assumed all worlds have the same win condition.
        # This might not be true in the future
        def won(state):
            if state.world.triforce_hunt:
                return state.has('Triforce Piece', state.world.triforce_count)
            else:
                return state.has('Triforce')

        # Check if already beaten
        if all(map(won, self.state_list)):
            return True

        if scan_for_items:
            # collect all available items
            # make a new search since we might be iterating over one already
            search = self.copy()
            search.collect_locations()
            # if every state got the Triforce, then return True
            return all(map(won, search.state_list))
        else:
            return False

    # Use the cache in the search to determine region reachability.
    # Implicitly requires is_starting_age or Time_Travel.
    def can_reach(self, region, age=None, tod=TimeOfDay.NONE):
        if age == 'adult':
            if tod:
                return region in self._cache['adult_regions'] and (self._cache['adult_regions'][region] & tod or self._expand_tod_regions(self._cache['adult_regions'], region, age, tod))
            else:
                return region in self._cache['adult_regions']
        elif age == 'child':
            if tod:
                return region in self._cache['child_regions'] and (self._cache['child_regions'][region] & tod or self._expand_tod_regions(self._cache['child_regions'], region, age, tod))
            else:
                return region in self._cache['child_regions']
        elif age == 'both':
            return self.can_reach(region, age='adult', tod=tod) and self.can_reach(region, age='child', tod=tod)
        else:
            # treat None as either
            return self.can_reach(region, age='adult', tod=tod) or self.can_reach(region, age='child', tod=tod)


    # Use the cache in the search to determine location reachability.
    # Only works for locations that had progression items...
    def visited(self, location):
        return location in self._cache['visited_locations']

    # Use the cache in the search to get all reachable regions.
    def reachable_regions(self, age=None):
        if age == 'adult':
            return self._cache['adult_regions'].keys()
        elif age == 'child':
            return self._cache['child_regions'].keys()
        else:
            return self._cache['adult_regions'].keys() + self._cache['child_regions'].keys()

    # Returns whether the given age can access the spot at this age and tod,
    # by checking whether the search has reached the containing region, and evaluating the spot's access rule.
    def spot_access(self, spot, age=None, tod=TimeOfDay.NONE):
        if age == 'adult' or age == 'child':
            return (self.can_reach(spot.parent_region, age=age, tod=tod)
                    and spot.access_rule(self.state_list[spot.world.id], spot=spot, age=age, tod=tod))
        elif age == 'both':
            return (self.can_reach(spot.parent_region, age=age, tod=tod)
                    and spot.access_rule(self.state_list[spot.world.id], spot=spot, age='adult', tod=tod)
                    and spot.access_rule(self.state_list[spot.world.id], spot=spot, age='child', tod=tod))
        else:
            return (self.can_reach(spot.parent_region, age='adult', tod=tod)
                    and spot.access_rule(self.state_list[spot.world.id], spot=spot, age='adult', tod=tod)) or (
                            self.can_reach(spot.parent_region, age='child', tod=tod)
                            and spot.access_rule(self.state_list[spot.world.id], spot=spot, age='child', tod=tod))


class RewindableSearch(Search):

    def unvisit(self, location):
        # A location being unvisited is either:
        # in the top two caches (if it's the first being unvisited for a sphere)
        # in the topmost cache only (otherwise)
        # After we unvisit every location in a sphere, the top two caches have identical visited locations.
        assert location in self.cached_spheres[-1]['visited_locations']
        if location in self.cached_spheres[-2]['visited_locations']:
            self.cached_spheres.pop()
            self._cache = self.cached_spheres[-1]
        self._cache['visited_locations'].discard(location)


    def reset(self):
        self._cache = self.cached_spheres[0]
        self.cached_spheres[1:] = []


    # Adds a new layer to the sphere cache, as a copy of the previous.
    def checkpoint(self):
        # Save the current data into the cache.
        self.cached_spheres.append({
            k: copy.copy(v) for k, v in self._cache.items()
        })
        self._cache = self.cached_spheres[-1]
