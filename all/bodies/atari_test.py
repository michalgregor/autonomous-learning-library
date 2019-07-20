import unittest
import torch
import torch_testing as tt
import numpy as np
from all.agents import Agent
from all.environments import GymEnvironment, State
from all.bodies.atari import DeepmindAtariBody, ToLegacyBody

NOOP_ACTION = torch.tensor([0])
INITIAL_ACTION = torch.tensor([3])
ACT_ACTION = torch.tensor([4])

class MockAgent(Agent):
    def __init__(self):
        self.state = None
        self.reward = None
        self.info = None

    def initial(self, state):
        self.state = state
        return INITIAL_ACTION

    def act(self, state, reward):
        self.state = state
        self.reward = reward
        return ACT_ACTION

    def terminal(self, reward):
        self.reward = reward

class ALE():
    def lives(self):
        return 1

class Unwrapped():
    ale = ALE()
    def get_action_meanings(self):
        return ['TEST', 'ACTIONS']

class InnerEnv():
    unwrapped = Unwrapped()

class MockEnv():
    _env = InnerEnv()

class DeepmindAtariBodyTest(unittest.TestCase):
    def setUp(self):
        self.agent = MockAgent()
        self.env = MockEnv()
        self.body = DeepmindAtariBody(ToLegacyBody(self.agent), self.env, noop_max=0)

    def test_initial_state(self):
        frame = State(torch.ones((1, 3, 4, 4)))
        action = self.body.initial(frame)
        tt.assert_equal(action, INITIAL_ACTION)
        tt.assert_equal(self.agent.state.features, torch.ones(1, 4, 2, 2))

    def test_deflicker(self):
        frame1 = State(torch.ones((1, 3, 4, 4)))
        frame2 = State(torch.ones((1, 3, 4, 4)))
        frame3 = State(torch.ones((1, 3, 4, 4)) * 2)
        self.body.act(frame1, 0)
        self.body.act(frame2, 0)
        self.body.act(frame3, 0)
        self.body.act(frame2, 0)
        self.body.act(frame2, 0)
        expected = torch.cat((
            torch.ones(1, 2, 2),
            torch.ones(2, 2, 2) * 2,
            torch.ones(1, 2, 2)
        )).unsqueeze(0)
        tt.assert_equal(self.agent.state.features, expected)

class DeepmindAtariBodyPongTest(unittest.TestCase):
    def setUp(self):
        self.agent = MockAgent()
        self.env = GymEnvironment('PongNoFrameskip-v4')
        self.body = DeepmindAtariBody(ToLegacyBody(self.agent), self.env, noop_max=0)

    def test_initial_state(self):
        self.env.reset()
        action = self.body.act(self.env.state, 0)
        tt.assert_equal(action, torch.tensor([1])) # fire on reset 1

    def test_second_state(self):
        self.env.reset()
        self.env.step(self.body.act(self.env.state, 0))
        action = self.body.act(self.env.state, self.env.reward)
        tt.assert_equal(action, torch.tensor([2])) # fire on reset 2

    def test_several_steps(self):
        self.env.reset()
        self.env.step(self.body.act(self.env.state, 0))
        self.env.step(self.body.act(self.env.state, -5))
        for _ in range(4):
            action = self.body.act(self.env.state, -5)
            self.assertEqual(self.agent.state.features.shape, (1, 4, 105, 80))
            tt.assert_equal(action, INITIAL_ACTION)
            self.env.step(action)
        for _ in range(10):
            reward = -5  # should be clipped
            self.assertEqual(self.agent.state.features.shape, (1, 4, 105, 80))
            action = self.body.act(self.env.state, reward)
            tt.assert_equal(action, ACT_ACTION)
            self.env.step(action)
        self.assertEqual(self.agent.reward, -4)

    def test_terminal_state(self):
        self.env.reset()
        self.env.step(self.body.act(self.env.state, 0))
        for _ in range(11):
            reward = -5  # should be clipped
            action = self.body.act(self.env.state, reward)
            self.env.step(action)
        # pylint: disable=protected-access
        self.env.state._mask = torch.tensor([0])
        self.body.act(self.env.state, -1)
        tt.assert_equal(action, ACT_ACTION)
        self.assertEqual(self.agent.state.features.shape, (1, 4, 105, 80))
        self.assertEqual(self.agent.reward, -4)

class NoFramestackTest(unittest.TestCase):
    def setUp(self):
        self.agent = MockAgent()
        self.env = GymEnvironment('PongNoFrameskip-v4')
        self.body = DeepmindAtariBody(ToLegacyBody(self.agent), self.env, noop_max=0, frame_stack=1)

    def test_several_steps(self):
        self.env.reset()
        self.env.step(self.body.act(self.env.state, 0))
        self.env.step(self.body.act(self.env.state, -5))
        for _ in range(10):
            self.body.act(self.env.state, -5)
            self.assertEqual(self.agent.state.features.shape, (1, 1, 105, 80))

class NoopTest(unittest.TestCase):
    def setUp(self):
        np.random.seed(0)
        self.agent = MockAgent()
        self.env = MockEnv()
        self.frame = State(torch.ones((1, 3, 4, 4)))
        self.body = DeepmindAtariBody(ToLegacyBody(self.agent), self.env, noop_max=10)

    def test_noops(self):
        action = self.body.act(self.frame, 0)
        tt.assert_equal(action, torch.tensor([0]))
        for _ in range(5):
            action = self.body.act(self.frame, 0)
            tt.assert_equal(action, torch.tensor([0]))
        for _ in range(4):
            action = self.body.act(self.frame, 0)
            tt.assert_equal(action, INITIAL_ACTION)
        for _ in range(4):
            action = self.body.act(self.frame, 0)
            tt.assert_equal(action, ACT_ACTION)

if __name__ == '__main__':
    unittest.main()