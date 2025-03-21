import pickle
import numpy as np
import random
from collections import deque, defaultdict
from examples.paper_io.algorithm.base_agent import BaseAgent

class QLAgent(BaseAgent):
    def __init__(self, env, learning_rate=0.01, discount_factor=0.99,
                 epsilon=1.0, epsilon_decay=0.9995, min_epsilon=0.1, 
                 n_step=5, replay_size=5000, batch_size=64, lambda_value=0.8, load_only=False):
        super().__init__(env)
        self.learning_rate = learning_rate
        self.discount_factor = discount_factor
        self.epsilon = epsilon
        self.epsilon_decay = epsilon_decay
        self.min_epsilon = min_epsilon
        self.n_step = n_step  
        self.batch_size = batch_size  
        self.q_table = defaultdict(float)  
        self.replay_buffer = deque(maxlen=replay_size)  
        self.n_step_buffer = deque(maxlen=n_step)
        self.lambda_value = lambda_value  
        self.e_trace = defaultdict(float)  
        self.load_only = load_only

    def get_state(self, observation, player_idx):
        grid = observation[player_idx]
        player = self.env.players[player_idx]
        player_id = player['id']
        x_local, y_local = player['position']

        cell_value = grid[x_local, y_local]
        position_status = (
            'on_territory' if cell_value == player_id else
            'on_trail' if cell_value == -player_id else
            'in_neutral'
        )
        trail_length = min(len(player['trail']), 5)
        nearest_enemy_distance = min(self._get_nearest_enemy_distance(grid, player_id, x_local, y_local), 10)
        nearest_enemy_direction = self._get_nearest_enemy_direction(grid, player_id, x_local, y_local)

        return (position_status, trail_length, nearest_enemy_direction, nearest_enemy_distance)

    def get_action(self, observation, player_idx):
        if not self.env.alive[player_idx]:
            return None

        state = self.get_state(observation, player_idx)
        num_actions = self.env.action_spaces[player_idx].n
        q_values = np.array([self.q_table[(state, a)] for a in range(num_actions)])

        tau = max(0.1, self.epsilon)
        q_values = q_values - np.max(q_values)  
        exp_q = np.exp(q_values / tau)
        probabilities = exp_q / np.sum(exp_q)

        return np.random.choice(num_actions, p=probabilities)

    def update(self, state, action, reward, next_state, done, player_idx):
        if self.load_only:
            return

        self.n_step_buffer.append((state, action, reward))
        self.e_trace[(state, action)] += 1  

        max_future_q = 0 if done else max(self.q_table[(next_state, a)] for a in range(self.env.action_spaces[player_idx].n))
        td_error = reward + self.discount_factor * max_future_q - self.q_table[(state, action)]

        for (s, a), trace_value in list(self.e_trace.items()):
            self.q_table[(s, a)] += self.learning_rate * td_error * trace_value
            self.e_trace[(s, a)] *= self.discount_factor * self.lambda_value  

        # **Capping Eligibility Traces to prevent excessive memory usage**
        if len(self.e_trace) > 500:
            self.e_trace.pop(next(iter(self.e_trace)))

        if len(self.n_step_buffer) == self.n_step:
            G = sum(self.discount_factor ** i * r for i, (_, _, r) in enumerate(self.n_step_buffer))
            s, a, _ = self.n_step_buffer.popleft()
            self.replay_buffer.append((s, a, G, next_state, done))

        if len(self.replay_buffer) >= self.batch_size:
            self._update_from_replay(player_idx)

        # **Ensure buffer is cleared at episode end**
        if done:
            self.n_step_buffer.clear()
            self.e_trace.clear()

    def _update_from_replay(self, player_idx):
        if len(self.replay_buffer) < self.batch_size:
            return  

        batch = random.sample(self.replay_buffer, self.batch_size)
        for state, action, reward, next_state, done in batch:
            current_q = self.q_table[(state, action)]
            max_future_q = 0 if done else max(self.q_table[(next_state, a)] for a in range(self.env.action_spaces[player_idx].n))
            td_error = reward + self.discount_factor * max_future_q - current_q
            self.q_table[(state, action)] += self.learning_rate * td_error

    def _normalize_q_table(self):
        q_values = np.array(list(self.q_table.values()))
        if q_values.size == 0 or np.all(q_values == q_values[0]):  
            return
        min_q, max_q = np.min(q_values), np.max(q_values)
        if max_q - min_q > 1e-5:
            scale = max_q - min_q
            for key in self.q_table:
                self.q_table[key] = (self.q_table[key] - min_q) / scale

    def decay_epsilon(self):
        self.epsilon = max(self.min_epsilon, self.epsilon * self.epsilon_decay)

    def save(self, filepath):
        try:
            with open(filepath, 'wb') as f:
                pickle.dump(dict(self.q_table), f)
            print(f"Q-table saved to {filepath}")
        except Exception as e:
            print(f"Error saving Q-table: {e}")

    def load(self, filepath):
        try:
            with open(filepath, 'rb') as f:
                self.q_table.update(pickle.load(f))
            print(f"Q-table loaded from {filepath}")
        except FileNotFoundError:
            print(f"Q-table file {filepath} not found. Starting fresh.")
        except Exception as e:
            print(f"Error loading Q-table: {e}")

    def _get_nearest_enemy_distance(self, grid, player_id, x_local, y_local):
        enemy_mask = (grid > 0) & (grid != player_id)
        enemy_positions = np.argwhere(enemy_mask)
        if enemy_positions.size == 0:
            return self.env.grid_size * 2
        distances = np.abs(enemy_positions - np.array([x_local, y_local])).sum(axis=1)
        return distances.min()

    def _get_nearest_enemy_direction(self, grid, player_id, x_local, y_local):
        enemy_mask = (grid > 0) & (grid != player_id)
        enemy_positions = np.argwhere(enemy_mask)
        if enemy_positions.size == 0:
            return 'none'
        differences = enemy_positions - np.array([x_local, y_local])
        distances = np.abs(differences).sum(axis=1)
        min_idx = distances.argmin()
        dx, dy = differences[min_idx]
        if abs(dx) > abs(dy):
            return 'down' if dx > 0 else 'up'
        elif abs(dy) > 0:
            return 'right' if dy > 0 else 'left'
        return 'none'
