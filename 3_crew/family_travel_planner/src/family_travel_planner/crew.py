from __future__ import annotations

from typing import List, Optional

from crewai import Agent, Crew, Process, Task
from crewai.agents.agent_builder.base_agent import BaseAgent
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import SerperDevTool
from crewai.memory.unified_memory import Memory
from crewai.memory.storage.lancedb_storage import LanceDBStorage
from pydantic import BaseModel, Field

@CrewBase
class FamilyTravelPlanner():
    """FamilyTravelPlanner crew"""

    agents: list[BaseAgent]
    tasks: list[Task]

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    # --- Output models ---
    class AirbnbOption(BaseModel):
        name: str
        link: str
        why_fit: str = Field(description="Why this listing fits the family (2-4 bullets in a single string).")
        bedrooms: Optional[str] = Field(default=None, description="Bedrooms / sleeping capacity if available.")
        key_amenities: Optional[str] = Field(
            default=None, description="Amenities visible in listing snippet (kitchen/parking/etc.)."
        )

    class AirbnbShortlist(BaseModel):
        options: List[AirbnbOption]

    class NearbyPlace(BaseModel):
        name: str
        category: str
        why_good_for_kids: str = Field(description="2-3 short sentences.")
        best_for_ages: str
        link: Optional[str] = None

    class PlacesShortlist(BaseModel):
        places: List[NearbyPlace]

    class DailyPlan(BaseModel):
        day_number: int
        date: str
        morning: str
        midday_break: str
        afternoon: str
        evening: str
        rainy_day_backup: str
        distance_notes: str = Field(
            description="Approx distances / travel times between the day's stops (morning->midday->afternoon->evening)."
        )

    class Itinerary(BaseModel):
        origin: str
        transport_modes: List[str] = Field(description="Selected travel modes, e.g. ['car','train','air'].")
        travel_options: List[str] = Field(
            description="Suggested travel options from origin to destination considering selected modes."
        )
        destination: str
        start_date: str
        end_date: str
        adults_count: int
        kids_count: int
        kids_ages: List[int]
        n_days: int

        top_airbnb_options: List[AirbnbOption]
        nearby_places: List[NearbyPlace]
        daily_plans: List[DailyPlan]

        packing_list: List[str] = Field(default_factory=list)
        travel_tips: List[str] = Field(default_factory=list)
        assumptions: List[str] = Field(default_factory=list)

    # Learn more about YAML configuration files here:
    # Agents: https://docs.crewai.com/concepts/agents#yaml-configuration-recommended
    # Tasks: https://docs.crewai.com/concepts/tasks#yaml-configuration-recommended
    
    # If you would like to add tools to your agents, you can learn more about it here:
    # https://docs.crewai.com/concepts/agents#agent-tools
    @agent
    def airbnb_finder(self) -> Agent:
        return Agent(
            config=self.agents_config["airbnb_finder"],  # type: ignore[index]
            tools=[SerperDevTool()],
            verbose=False,
        )

    @agent
    def nearby_places_finder(self) -> Agent:
        return Agent(
            config=self.agents_config["nearby_places_finder"],  # type: ignore[index]
            tools=[SerperDevTool()],
            verbose=False,
        )

    @agent
    def itinerary_builder(self) -> Agent:
        return Agent(
            config=self.agents_config["itinerary_builder"],  # type: ignore[index]
            verbose=False,
        )

    # To learn more about structured task outputs,
    # task dependencies, and task callbacks, check out the documentation:
    # https://docs.crewai.com/concepts/tasks#overview-of-a-task
    @task
    def find_airbnb_options(self) -> Task:
        return Task(
            config=self.tasks_config["find_airbnb_options"],  # type: ignore[index]
            output_pydantic=self.AirbnbShortlist,
        )

    @task
    def find_nearby_places(self) -> Task:
        return Task(
            config=self.tasks_config["find_nearby_places"],  # type: ignore[index]
            output_pydantic=self.PlacesShortlist,
        )

    @task
    def build_kid_friendly_itinerary(self) -> Task:
        return Task(
            config=self.tasks_config["build_kid_friendly_itinerary"],  # type: ignore[index]
            output_pydantic=self.Itinerary,
            context=[self.find_airbnb_options(), self.find_nearby_places()],
        )

    @crew
    def crew(self) -> Crew:
        """Creates the FamilyTravelPlanner crew"""
        # To learn how to add knowledge sources to your crew, check out the documentation:
        # https://docs.crewai.com/concepts/knowledge#what-is-knowledge

        memory = Memory(
            storage=LanceDBStorage(path="./memory"),
            embedder={"provider": "openai", "config": {"model": "text-embedding-3-small"}},
        )

        return Crew(
            agents=[
                self.airbnb_finder(),
                self.nearby_places_finder(),
                self.itinerary_builder(),
            ],
            tasks=[
                self.find_airbnb_options(),
                self.find_nearby_places(),
                self.build_kid_friendly_itinerary(),
            ],
            process=Process.sequential,
            verbose=True,
            memory=memory,
            # process=Process.hierarchical, # In case you wanna use that instead https://docs.crewai.com/how-to/Hierarchical/
        )
