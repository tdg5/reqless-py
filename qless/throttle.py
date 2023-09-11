import simplejson as json


class Throttle:
    def __init__(self, client, name):
        self.client = client
        self.name = name

    def delete(self):
        self.client('throttle.delete', self.name)

    def locks(self):
        return self.client('throttle.locks', self.name)

    def maximum(self):
        json_state = self.client('throttle.get', self.name)
        state = json.loads(json_state) if json_state else {}
        return state.get('maximum', 0)

    def set_maximum(self, maximum, expiration=None):
        _maximum = maximum if maximum is not None else self.maximum()
        self.client('throttle.set', self.name, _maximum, expiration or 0)

    def pending(self):
        return self.client('throttle.pending', self.name)

    def ttl(self):
        return self.client('throttle.ttl', self.name)
