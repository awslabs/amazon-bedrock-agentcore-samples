#!/usr/bin/env python3
import aws_cdk as cdk
from weather_agent_stack import WeatherAgentStack

app = cdk.App()
WeatherAgentStack(app, "WeatherAgentDemo")

app.synth()
