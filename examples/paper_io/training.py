import os
import matplotlib.pyplot as plt
import numpy as np
import sys
from examples.paper_io.utils.agent_colors import assign_agent_colors
from examples.paper_io.utils.plots import (
    plot_average_self_eliminations, plot_cumulative_self_eliminations, plot_epsilon_decay, plot_steps_per_episode, plot_td_error, plot_total_self_eliminations_per_episode,
    plot_training_progress, plot_agent_wins, plot_agent_eliminations,
)
import pygame  # Import pygame for rendering only if necessary

from Paper_io_develop import PaperIoEnv
from examples.paper_io.algorithm.Q_Learining.q_learning_agent import QLearningAgent

# Set the flag for rendering the environment
render_game = False  # Set to True if you want to render the game during training

# Create the environment
env = PaperIoEnv(render=render_game)

# Assign random colors to agents
color_info = assign_agent_colors(env.num_players)
agent_colors = [info[0] for info in color_info]  # RGB values for rendering
agent_color_names = [info[1] for info in color_info]  # Color names for logging

# Choose the policy
agent = QLearningAgent(env)
policy_name = 'q_learning'

# Training variables
num_episodes = 30000
steps_per_episode = 400
episode_rewards = []
moving_avg_rewards = []
steps_per_episode_list = []
epsilon_values = []
episodes = []
self_eliminations_per_episode = []  # Track self-eliminations per episode

window_size = 50  # For smoothing graphs
loading_bar_length = 20;  # Length of the loading bar

# Initialize cumulative counts
agent_wins = [0 for _ in range(env.num_players)]
agent_eliminations = [0 for _ in range(env.num_players)]
agent_self_eliminations = [0 for _ in range(env.num_players)]

# Function to find the next available folder index
def get_next_model_index(models_dir, policy_name):
    existing_folders = [d for d in os.listdir(models_dir) if policy_name in d]
    if existing_folders:
        indices = [int(folder.split('_')[-1]) for folder in existing_folders if folder.split('_')[-1].isdigit()]
        return max(indices) + 1 if indices else 1
    else:
        return 1

# Initialize model count based on policy name
models_dir = 'models'
os.makedirs(models_dir, exist_ok=True)

# Determine the next folder name
model_count = get_next_model_index(models_dir, policy_name)
model_folder_name = f"{policy_name}_{model_count}"

# Create directories for the new model
model_folder = os.path.join(models_dir, model_folder_name)
trained_model_folder = os.path.join(model_folder, 'trained_model')
plots_folder = os.path.join(model_folder, 'plots')
os.makedirs(trained_model_folder, exist_ok=True)
os.makedirs(plots_folder, exist_ok=True)

# File to save training details
training_info_file = os.path.join(model_folder, 'training_info.txt')

# Function to save training information
def save_training_info(file_path, num_episodes, steps_per_episode, agent, reward_config):
    with open(file_path, 'w') as f:
        f.write(f"Q-Learning Training Information\n")
        f.write(f"Policy Name: {policy_name}\n")
        f.write(f"Number of Episodes: {num_episodes}\n")
        f.write(f"Steps per Episode: {steps_per_episode}\n")
        f.write(f"Learning Rate: {agent.learning_rate}\n")
        f.write(f"Discount Factor: {agent.discount_factor}\n")
        f.write(f"Initial Epsilon: {1.0}\n")
        f.write(f"Final Epsilon: {agent.epsilon}\n")
        f.write(f"Epsilon Decay Rate: {agent.epsilon_decay}\n")
        f.write(f"Minimum Epsilon: {agent.min_epsilon}\n")
        f.write(f"------------------------------------\n")
        # Write statistics for each agent, grouping their stats together
        for idx in range(env.num_players):
            f.write(f"Total Wins for Agent {idx}: {agent_wins[idx]}\n")
            f.write(f"Total Eliminations by Agent {idx}: {agent_eliminations[idx]}\n")
            f.write(f"Total Self-Eliminations by Agent {idx}: {agent_self_eliminations[idx]}\n")
            f.write("\n")  # Add a blank line between agents for readability
        f.write(f"Agent Colors (Names): {agent_color_names}\n")
        f.write(f"Final Q-Table Path: {q_table_path}\n")
        # Reward information
        f.write("\nReward Information:\n")
        for key, value in env.reward_config.items():
            f.write(f"{key.replace('_', ' ').capitalize()}: {value}\n")
    print(f"Training information saved at {file_path}")

# Print the initial header
print(f"{'Epoch':<6} {'Progress':<23}")
print("=" * 30)

# Train the agent
episode_num = 0

while episode_num < num_episodes:
    obs = env.reset()
    episode_reward = 0

    for step in range(steps_per_episode):
        if render_game:
            env.render(agent_colors)

        # Get actions from the agent
        actions = agent.get_actions(obs)

        # Record the current state for each player
        states = []
        for i in range(env.num_players):
            if not env.alive[i]:
                states.append(None)
                continue
            state = agent.get_state(obs, i)
            states.append(state)

        # Take a step in the environment
        next_obs, rewards, done, info = env.step(actions)

        # Update total reward for the episode
        episode_reward += sum(rewards)

        # Record the next state for each player and update Q-values
        for i in range(env.num_players):
            if not env.alive[i]:
                continue
            next_state = agent.get_state(next_obs, i)
            agent.update_q_values(states[i], actions[i], rewards[i], next_state, done, i)

        obs = next_obs

        # Calculate and display loading progress
        if (step + 1) % max(1, (steps_per_episode // loading_bar_length)) == 0:
            progress_percentage = (step + 1) / steps_per_episode * 100
            loading_bar = "|" + "-" * int((step + 1) / (steps_per_episode / loading_bar_length)) + \
                          " " * (loading_bar_length - int((step + 1) / (steps_per_episode / loading_bar_length))) + "|"
            sys.stdout.write(f"\rEpoch {episode_num + 1:<5} {loading_bar} {int(progress_percentage)}%")
            sys.stdout.flush()

        if done:
            break

    # Finish the loading bar at the end of the episode
    loading_bar = "|" + "-" * loading_bar_length + "|"
    sys.stdout.write(f"\rEpoch {episode_num + 1:<5} {loading_bar} 100%\n")
    sys.stdout.flush()

    # Process info to update cumulative counts
    winners = info.get('winners', [])
    if winners:
        for winner in winners:
            agent_wins[winner] += 1

    eliminations = info.get('eliminations_by_agent', [])
    if eliminations:
        for i in range(env.num_players):
            agent_eliminations[i] += eliminations[i]

    self_eliminations = info.get('self_eliminations_by_agent', [])
    if self_eliminations:
        for i in range(env.num_players):
            agent_self_eliminations[i] += self_eliminations[i]

    # Track self-eliminations for the current episode
    self_eliminations_per_episode.append(info.get('self_eliminations_by_agent', [0] * env.num_players))

    # Store episode data
    episode_rewards.append(episode_reward)
    episodes.append(episode_num)
    steps_per_episode_list.append(step + 1)
    epsilon_values.append(agent.epsilon)

    # Calculate moving average reward
    if len(episode_rewards) >= window_size:
        moving_avg = np.mean(episode_rewards[-window_size:])
        moving_avg_rewards.append(moving_avg)
    else:
        moving_avg_rewards.append(np.mean(episode_rewards))

    # Decay epsilon after each episode
    agent.decay_epsilon()

    episode_num += 1

# Plotting
plot_training_progress(episodes, episode_rewards, moving_avg_rewards, plots_folder)
plot_steps_per_episode(episodes, steps_per_episode_list, plots_folder)
plot_epsilon_decay(episodes, epsilon_values, plots_folder)
plot_td_error(agent.td_errors, plots_folder)
plot_agent_wins(agent_wins, plots_folder)
plot_agent_eliminations(agent_eliminations, plots_folder)

plot_cumulative_self_eliminations(episodes, self_eliminations_per_episode, plots_folder)


plot_average_self_eliminations(episodes, self_eliminations_per_episode, plots_folder, window_size=window_size)


plot_total_self_eliminations_per_episode(episodes, self_eliminations_per_episode, plots_folder)

# Save the Q-table after training
q_table_path = os.path.join(trained_model_folder, 'q_table.pkl')
agent.save_q_table(q_table_path)
print(f"Q-table saved at {q_table_path}")

# Save the training information
save_training_info(training_info_file, num_episodes, steps_per_episode, agent, env.reward_config)

# Show the plots
plt.show()

# Cleanup pygame if rendering was enabled
if render_game:
    pygame.quit()

print("Training was Completed.")
