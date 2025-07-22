import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import base64
import io
from datetime import datetime

# Load the CSV data
df = pd.read_csv('AAPL.csv')

# Convert Date column to datetime
df['Date'] = pd.to_datetime(df['Date'])

# Sort by date to ensure proper chronological order
df = df.sort_values('Date')

# Calculate moving averages
df['MA_20'] = df['Close'].rolling(window=20).mean()
df['MA_50'] = df['Close'].rolling(window=50).mean()

# Calculate daily returns
df['Daily_Return'] = df['Close'].pct_change()

# Calculate volatility (30-day rolling standard deviation)
df['Volatility'] = df['Daily_Return'].rolling(window=30).std()

# Print basic statistics
print("AAPL Stock Analysis Summary")
print("=" * 40)
print(f"Data Range: {df['Date'].min().strftime('%Y-%m-%d')} to {df['Date'].max().strftime('%Y-%m-%d')}")
print(f"Total Trading Days: {len(df)}")
print(f"Average Close Price: ${df['Close'].mean():.2f}")
print(f"Highest Close Price: ${df['Close'].max():.2f}")
print(f"Lowest Close Price: ${df['Close'].min():.2f}")
print(f"Average Daily Volume: {df['Volume'].mean():,.0f}")
print(f"Average Daily Return: {df['Daily_Return'].mean()*100:.2f}%")
print(f"Daily Return Volatility: {df['Daily_Return'].std()*100:.2f}%")
print()

# Chart 1: Stock Price and Moving Averages
plt.figure(figsize=(14, 8))
plt.plot(df['Date'], df['Close'], label='Close Price', linewidth=1, alpha=0.8)
plt.plot(df['Date'], df['MA_20'], label='20-Day MA', linewidth=1, alpha=0.7)
plt.plot(df['Date'], df['MA_50'], label='50-Day MA', linewidth=1, alpha=0.7)
plt.title('AAPL Stock Price with Moving Averages', fontsize=16, fontweight='bold')
plt.xlabel('Date', fontsize=12)
plt.ylabel('Price ($)', fontsize=12)
plt.legend()
plt.grid(True, alpha=0.3)
plt.xticks(rotation=45)
plt.tight_layout()

buffer = io.BytesIO()
plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
buffer.seek(0)
image_base64 = base64.b64encode(buffer.read()).decode('utf-8')
plt.close()

print(f"IMAGE_DATA:{image_base64}")
print("Stock Price Chart generated successfully!")
print()

# Chart 2: Volume Analysis
plt.figure(figsize=(14, 6))
plt.bar(df['Date'], df['Volume'], alpha=0.7, color='steelblue')
plt.title('AAPL Trading Volume Over Time', fontsize=16, fontweight='bold')
plt.xlabel('Date', fontsize=12)
plt.ylabel('Volume', fontsize=12)
plt.xticks(rotation=45)
volume_ma = df['Volume'].rolling(window=20).mean()
plt.plot(df['Date'], volume_ma, color='red', linewidth=2, label='20-Day Volume MA')
plt.legend()
plt.grid(True, alpha=0.3)
plt.tight_layout()

buffer = io.BytesIO()
plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
buffer.seek(0)
image_base64 = base64.b64encode(buffer.read()).decode('utf-8')
plt.close()

print(f"IMAGE_DATA:{image_base64}")
print("Volume Chart generated successfully!")
print()

# Chart 3: Daily Returns Distribution
plt.figure(figsize=(12, 8))
plt.subplot(2, 2, 1)
plt.hist(df['Daily_Return'].dropna(), bins=50, alpha=0.7, color='green', edgecolor='black')
plt.title('Daily Returns Distribution')
plt.xlabel('Daily Return')
plt.ylabel('Frequency')
plt.grid(True, alpha=0.3)

plt.subplot(2, 2, 2)
plt.plot(df['Date'], df['Daily_Return'], alpha=0.7, color='green')
plt.title('Daily Returns Over Time')
plt.xlabel('Date')
plt.ylabel('Daily Return')
plt.xticks(rotation=45)
plt.grid(True, alpha=0.3)

plt.subplot(2, 2, 3)
plt.plot(df['Date'], df['Volatility'], color='red', alpha=0.8)
plt.title('30-Day Rolling Volatility')
plt.xlabel('Date')
plt.ylabel('Volatility')
plt.xticks(rotation=45)
plt.grid(True, alpha=0.3)

plt.subplot(2, 2, 4)
high_low_range = df['High'] - df['Low']
plt.plot(df['Date'], high_low_range, color='orange', alpha=0.7)
plt.title('Daily Price Range (High - Low)')
plt.xlabel('Date')
plt.ylabel('Price Range ($)')
plt.xticks(rotation=45)
plt.grid(True, alpha=0.3)

plt.tight_layout()

buffer = io.BytesIO()
plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
buffer.seek(0)
image_base64 = base64.b64encode(buffer.read()).decode('utf-8')
plt.close()

print(f"IMAGE_DATA:{image_base64}")
print("Returns and Volatility Analysis Chart generated successfully!")
print()

# Chart 4: Candlestick-style OHLC Chart
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), height_ratios=[3, 1])

# Price chart
for i in range(len(df)):
    color = 'green' if df.iloc[i]['Close'] >= df.iloc[i]['Open'] else 'red'
    ax1.plot([df.iloc[i]['Date'], df.iloc[i]['Date']], 
             [df.iloc[i]['Low'], df.iloc[i]['High']], 
             color='black', linewidth=0.5)
    ax1.plot([df.iloc[i]['Date'], df.iloc[i]['Date']], 
             [df.iloc[i]['Open'], df.iloc[i]['Close']], 
             color=color, linewidth=2, alpha=0.8)

ax1.set_title('AAPL OHLC Price Chart', fontsize=16, fontweight='bold')
ax1.set_ylabel('Price ($)', fontsize=12)
ax1.grid(True, alpha=0.3)

# Volume chart
colors = ['green' if df.iloc[i]['Close'] >= df.iloc[i]['Open'] else 'red' for i in range(len(df))]
ax2.bar(df['Date'], df['Volume'], color=colors, alpha=0.7, width=1)
ax2.set_title('Volume', fontsize=12)
ax2.set_xlabel('Date', fontsize=12)
ax2.set_ylabel('Volume', fontsize=12)
ax2.grid(True, alpha=0.3)

plt.xticks(rotation=45)
plt.tight_layout()

buffer = io.BytesIO()
plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
buffer.seek(0)
image_base64 = base64.b64encode(buffer.read()).decode('utf-8')
plt.close()

print(f"IMAGE_DATA:{image_base64}")
print("OHLC and Volume Chart generated successfully!")
print()

# Calculate and display additional insights
print("Additional Insights:")
print("=" * 20)

# Best and worst performing days
best_day = df.loc[df['Daily_Return'].idxmax()]
worst_day = df.loc[df['Daily_Return'].idxmin()]

print(f"Best performing day: {best_day['Date'].strftime('%Y-%m-%d')} ({best_day['Daily_Return']*100:.2f}%)")
print(f"Worst performing day: {worst_day['Date'].strftime('%Y-%m-%d')} ({worst_day['Daily_Return']*100:.2f}%)")

# High volume days
high_volume_threshold = df['Volume'].quantile(0.95)
high_volume_days = df[df['Volume'] > high_volume_threshold]
print(f"Days with exceptionally high volume (top 5%): {len(high_volume_days)}")

# Monthly performance
df['Year_Month'] = df['Date'].dt.to_period('M')
monthly_returns = df.groupby('Year_Month')['Daily_Return'].sum()
best_month = monthly_returns.idxmax()
worst_month = monthly_returns.idxmin()

print(f"Best performing month: {best_month} ({monthly_returns[best_month]*100:.2f}%)")
print(f"Worst performing month: {worst_month} ({monthly_returns[worst_month]*100:.2f}%)")

print("\nAnalysis complete! All charts have been generated.")