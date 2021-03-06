import numpy as np
import torch

__all__ = ['State', 'StateTensor']

class State(dict):
    def __init__(self, x, device='cpu', **kwargs):
        if not isinstance(x, dict):
            x = {'observation': x}
        for k, v in kwargs.items():
            x[k] = v
        if 'observation' not in x:
            raise Exception('State must contain an observation')
        if 'reward' not in x:
            x['reward'] = 0.
        if 'done' not in x:
            x['done'] = False
        if 'mask' not in x:
            x['mask'] = 1. - x['done']
        super().__init__(x)
        self.shape = ()
        self.device = device

    @classmethod
    def from_list(cls, list_of_states):
        device = list_of_states[0].device
        shape = (len(list_of_states), *list_of_states[0].shape)
        x = {}
        for key in list_of_states[0].keys():
            v = list_of_states[0][key]
            try:
                if torch.is_tensor(v):
                    x[key] = torch.stack([state[key] for state in list_of_states])
                else:
                    x[key] = torch.tensor([state[key] for state in list_of_states], device=device)
            except: # # pylint: disable=bare-except
                pass
        return StateTensor(x, shape, device=device)

    def apply(self, model, *keys):
        return self.apply_mask(self.as_output(model(*[self.as_input(key) for key in keys])))

    def as_input(self, key):
        return self[key].unsqueeze(0)

    def as_output(self, tensor):
        return tensor.squeeze(0)

    def apply_mask(self, tensor):
        return tensor * self.mask

    def update(self, key, value):
        x = {}
        for k in self.keys():
            if not k == key:
                x[k] = super().__getitem__(k)
        x[key] = value
        return self.__class__(x, device=self.device)

    @classmethod
    def from_gym(cls, state, device='cpu', dtype=np.float32):
        if not isinstance(state, tuple):
            return State({
                'observation': torch.from_numpy(
                    np.array(
                        state,
                        dtype=dtype
                    ),
                ).to(device)
            }, device=device)

        observation, reward, done, info = state
        observation = torch.from_numpy(
            np.array(
                observation,
                dtype=dtype
            ),
        ).to(device)
        x = {
            'observation': observation,
            'reward': float(reward),
            'done': done,
        }
        info = info if info else {}
        for key in info:
            x[key] = info[key]
        return State(x, device=device)

    @property
    def observation(self):
        return self['observation']

    @property
    def reward(self):
        return self['reward']

    @property
    def done(self):
        return self['done']

    @property
    def mask(self):
        return self['mask']

    def __len__(self):
        return 1

class StateTensor(State):
    def __init__(self, x, shape, device='cpu', **kwargs):
        if not isinstance(x, dict):
            x = {'observation': x}
        for k, v in kwargs.items():
            x[k] = v
        if 'observation' not in x:
            raise Exception('StateTensor must contain an observation')
        if 'reward' not in x:
            x['reward'] = torch.zeros(shape, device=device)
        if 'done' not in x:
            x['done'] = torch.tensor([False] * np.prod(shape), device=device).view(shape)
        if 'mask' not in x:
            x['mask'] = 1. - x['done'].float()
        super().__init__(x, device=device)
        self.shape = shape

    def update(self, key, value):
        x = {}
        for k in self.keys():
            if not k == key:
                x[k] = super().__getitem__(k)
        x[key] = value
        return self.__class__(x, self.shape, device=self.device)

    def as_input(self, key):
        value = self[key]
        return value.view((np.prod(self.shape), *value.shape[len(self.shape):])).float()

    def as_output(self, tensor):
        return tensor.view((*self.shape, *tensor.shape[1:]))

    def apply_mask(self, tensor):
        return tensor * self.mask.unsqueeze(-1) # pylint: disable=no-member

    def flatten(self):
        n = np.prod(self.shape)
        dims = len(self.shape)
        x = {}
        for k, v in self.items():
            x[k] = v.view((n, *v.shape[dims:]))
        return StateTensor(x, (n,), device=self.device)

    def view(self, shape):
        dims = len(self.shape)
        x = {}
        for k, v in self.items():
            x[k] = v.view((*shape, *v.shape[dims:]))
        return StateTensor(x, shape, device=self.device)

    @property
    def observation(self):
        return self['observation']

    @property
    def reward(self):
        return self['reward']

    @property
    def done(self):
        return self['done']

    @property
    def mask(self):
        return self['mask']

    def __getitem__(self, key):
        if isinstance(key, slice):
            shape = self['mask'][key].shape
            return StateTensor({k:v[key] for (k, v) in self.items()}, shape, device=self.device)
        if isinstance(key, int):
            return State({k:v[key] for (k, v) in self.items()}, device=self.device)
        if torch.is_tensor(key):
            # some things may get los
            d = {}
            shape = self['mask'][key].shape
            for (k, v) in self.items():
                try:
                    d[k] = v[key]
                except: # pylint: disable=bare-except
                    pass
            return self.__class__(d, shape, device=self.device)
        try:
            value = super().__getitem__(key)
        except KeyError:
            return None
        return value

    def __len__(self):
        return self.shape[0]
