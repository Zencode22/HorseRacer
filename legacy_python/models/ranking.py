# ============================================================================
# RANKING SYSTEM
# ============================================================================

import time
import json
import os
from typing import List, Dict, Tuple
from models.vector2 import Vector2
from utils.colors import COLORS

class HorseStats:
    """Tracks statistics for a single horse"""
    
    def __init__(self, horse_id: int, color: Tuple[int, int, int], name: str = ""):
        self.horse_id = horse_id
        self.color = color
        self.name = name
        self.laps_completed = 0
        self.reset_count = 0
        self.total_distance = 0.0
        self.lap_times = []
        self.current_lap_start_time = None
        self.finish_time = None
        self.best_lap_time = float('inf')
        self.worst_lap_time = 0.0
        self.average_lap_time = 0.0
        self.checkpoints_reached = 0
        self.ranking_score = 0.0
        self.finished = False
        self.paused_time = 0.0
        
    def start_new_lap(self):
        self.current_lap_start_time = time.time()
        
    def complete_lap(self, path_percentage: float = None):
        if self.current_lap_start_time is None:
            return
            
        lap_time = time.time() - self.current_lap_start_time
        self.lap_times.append(lap_time)
        self.laps_completed += 1
        
        if lap_time < self.best_lap_time:
            self.best_lap_time = lap_time
        if lap_time > self.worst_lap_time:
            self.worst_lap_time = lap_time
            
        if self.lap_times:
            self.average_lap_time = sum(self.lap_times) / len(self.lap_times)
        
        self.update_ranking_score()
        
    def finish_race(self, path_percentage: float = None):
        if self.current_lap_start_time and not self.finished:
            self.finish_time = time.time() - self.current_lap_start_time
            self.finished = True
            self.complete_lap(path_percentage)
            
    def add_reset(self):
        self.reset_count += 1
        self.update_ranking_score()
        
    def update_distance(self, distance: float):
        self.total_distance += distance
        
    def reached_checkpoint(self):
        self.checkpoints_reached += 1
        
    def update_ranking_score(self):
        if self.finish_time is not None:
            time_score = self.finish_time
        elif self.average_lap_time > 0:
            time_score = self.average_lap_time
        elif self.best_lap_time < float('inf'):
            time_score = self.best_lap_time
        else:
            time_score = 1000.0
        
        reset_penalty = self.reset_count * 5.0
        incomplete_penalty = 0.0 if self.finished else 50.0
        
        self.ranking_score = time_score + reset_penalty + incomplete_penalty
        
    def get_stats_dict(self) -> Dict:
        return {
            'horse_id': self.horse_id,
            'name': self.name,
            'color': self.color,
            'laps_completed': self.laps_completed,
            'reset_count': self.reset_count,
            'total_distance': self.total_distance,
            'lap_times': self.lap_times,
            'finish_time': self.finish_time,
            'best_lap_time': self.best_lap_time,
            'worst_lap_time': self.worst_lap_time,
            'average_lap_time': self.average_lap_time,
            'checkpoints_reached': self.checkpoints_reached,
            'ranking_score': self.ranking_score,
            'finished': self.finished,
        }
    
    def load_from_dict(self, data: Dict):
        self.name = data.get('name', '')
        self.laps_completed = data.get('laps_completed', 0)
        self.reset_count = data.get('reset_count', 0)
        self.total_distance = data.get('total_distance', 0.0)
        self.lap_times = data.get('lap_times', [])
        self.finish_time = data.get('finish_time', None)
        self.best_lap_time = data.get('best_lap_time', float('inf'))
        self.worst_lap_time = data.get('worst_lap_time', 0.0)
        self.average_lap_time = data.get('average_lap_time', 0.0)
        self.checkpoints_reached = data.get('checkpoints_reached', 0)
        self.ranking_score = data.get('ranking_score', 0.0)
        self.finished = data.get('finished', False)


class RankingManager:
    """Manages rankings for all horses"""
    
    def __init__(self):
        self.horse_stats = {}
        self.rankings = []
        self.save_file = "horse_rankings.json"
        self.race_start_time = None
        self.race_finished = False
        self.winner = None
        self.paused = False
        self.pause_start_time = None
        self.total_paused_time = 0.0
        self._final_time = None
        self.load_rankings()
        
    def start_race(self):
        self.race_start_time = time.time()
        self.race_finished = False
        self.winner = None
        self.total_paused_time = 0.0
        self._final_time = None
        for stats in self.horse_stats.values():
            stats.finished = False
            stats.finish_time = None
            
    def pause_race(self):
        if not self.paused and not self.race_finished:
            self.paused = True
            self.pause_start_time = time.time()
            
    def resume_race(self):
        if self.paused and self.pause_start_time:
            pause_duration = time.time() - self.pause_start_time
            self.total_paused_time += pause_duration
            self.paused = False
            self.pause_start_time = None
            
    def register_horse(self, horse_id: int, color: Tuple[int, int, int], name: str = ""):
        if horse_id not in self.horse_stats:
            self.horse_stats[horse_id] = HorseStats(horse_id, color, name)
            self.update_rankings()
        else:
            # Update name if already registered
            self.horse_stats[horse_id].name = name
            
    def start_lap(self, horse_id: int):
        if horse_id in self.horse_stats and not self.horse_stats[horse_id].finished:
            self.horse_stats[horse_id].start_new_lap()
            
    def complete_lap(self, horse_id: int, path_percentage: float = None):
        if horse_id in self.horse_stats and not self.horse_stats[horse_id].finished:
            self.horse_stats[horse_id].complete_lap(path_percentage)
            self.update_rankings()
            self.save_rankings()
            
    def finish_race(self, horse_id: int, path_percentage: float = None):
        if horse_id in self.horse_stats:
            stats = self.horse_stats[horse_id]
            if not stats.finished:
                if stats.current_lap_start_time:
                    stats.finish_time = time.time() - stats.current_lap_start_time
                else:
                    stats.finish_time = self.get_race_time()
                
                stats.finished = True
                stats.complete_lap(path_percentage)
                self.update_rankings()
                self.save_rankings()
                
                if self.winner is None:
                    self.winner = horse_id
                    print(f"\nWINNER! {stats.name} finished first in {stats.finish_time:.2f} seconds!")
                
                all_finished = all(stats.finished for stats in self.horse_stats.values())
                if all_finished:
                    self.race_finished = True
                    self._final_time = self.get_race_time()
                    print("\nRACE COMPLETE! All horses have finished.")
                    print(f"Final race time: {self._final_time:.2f} seconds")
                    self.print_final_results()
    
    def add_reset(self, horse_id: int):
        if horse_id in self.horse_stats:
            self.horse_stats[horse_id].add_reset()
            self.update_rankings()
            
    def reached_checkpoint(self, horse_id: int):
        if horse_id in self.horse_stats:
            self.horse_stats[horse_id].reached_checkpoint()
            
    def update_distance(self, horse_id: int, distance: float):
        if horse_id in self.horse_stats:
            self.horse_stats[horse_id].update_distance(distance)
            
    def update_rankings(self):
        rankings_list = []
        for horse_id, stats in self.horse_stats.items():
            rankings_list.append((stats.ranking_score, horse_id))
        
        rankings_list.sort()
        self.rankings = rankings_list
        
    def get_rank(self, horse_id: int) -> int:
        for i, (_, hid) in enumerate(self.rankings):
            if hid == horse_id:
                return i + 1
        return len(self.rankings) + 1
        
    def get_top_horses(self, count: int = 3) -> List[Tuple[int, float]]:
        return [(hid, score) for score, hid in self.rankings[:count]]
        
    def get_horse_stats(self, horse_id: int) -> HorseStats:
        return self.horse_stats.get(horse_id)
    
    def get_finish_time(self, horse_id: int) -> float:
        stats = self.horse_stats.get(horse_id)
        if stats and stats.finished:
            return stats.finish_time
        return None
        
    def get_race_time(self) -> float:
        if self.race_start_time is None:
            return 0.0
        
        if self.race_finished and self._final_time is not None:
            return self._final_time
        
        if self.paused and self.pause_start_time:
            return self.pause_start_time - self.race_start_time - self.total_paused_time
        else:
            return time.time() - self.race_start_time - self.total_paused_time
        
    def save_rankings(self):
        try:
            data = {'horses': {}}
            for horse_id, stats in self.horse_stats.items():
                data['horses'][str(horse_id)] = stats.get_stats_dict()
            
            with open(self.save_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving rankings: {e}")
            
    def load_rankings(self):
        try:
            if os.path.exists(self.save_file):
                with open(self.save_file, 'r') as f:
                    data = json.load(f)
                
                for horse_id_str, stats_data in data.get('horses', {}).items():
                    horse_id = int(horse_id_str)
                    stats = HorseStats(horse_id, (0,0,0), '')
                    stats.load_from_dict(stats_data)
                    self.horse_stats[horse_id] = stats
                
                self.update_rankings()
        except Exception as e:
            print(f"Error loading rankings: {e}")
            
    def reset_all_stats(self):
        self.horse_stats.clear()
        self.rankings.clear()
        self.race_start_time = None
        self.race_finished = False
        self.winner = None
        self.paused = False
        self.pause_start_time = None
        self.total_paused_time = 0.0
        self._final_time = None
        self.save_rankings()
        
    def print_final_results(self):
        print("\n" + "="*70)
        print("FINAL RACE RESULTS")
        print("="*70)
        
        finished_horses = [(stats.finish_time, hid) for hid, stats in self.horse_stats.items() if stats.finished]
        finished_horses.sort()
        
        for i, (finish_time, hid) in enumerate(finished_horses):
            stats = self.horse_stats[hid]
            print(f"{i+1:2d}. {stats.name:8s} | {finish_time:7.2f}s | tries {stats.reset_count}")
        
        print("="*70)
        
    def get_ranking_summary(self) -> List[str]:
        summary = []
        for i, (score, horse_id) in enumerate(self.rankings[:5]):
            stats = self.horse_stats[horse_id]
            finish_str = f"{stats.finish_time:.2f}s" if stats.finish_time else "---"
            summary.append(f"{i+1}. {stats.name:8s} | {finish_str} | tries {stats.reset_count}")
        return summary