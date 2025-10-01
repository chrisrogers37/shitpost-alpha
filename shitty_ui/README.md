# 🇺🇸 Shitty UI - America's Premier Trading Dashboard 🇺🇸

**Real-time visualization of Shitpost Alpha trading signals with obnoxiously American flair!**

## 🎯 Overview

The Shitty UI is a Plotly Dash dashboard that displays Trump's Truth Social posts alongside their LLM-generated market predictions. Built with maximum American patriotism and designed to make you feel like you're trading from the Oval Office!

## 🚀 Features

- **🇺🇸 Live Shitpost Feed** - Real-time display of Truth Social posts with predictions
- **🎯 Advanced Filtering** - Filter by predictions, assets, confidence, and date ranges
- **📊 Trading Analytics** - Sentiment and confidence distribution charts
- **⚡ Auto-Refresh** - Updates every 5 minutes to match the pipeline schedule
- **🎨 Obnoxiously American Theme** - Red, white, and blue styling with patriotic icons
- **📱 Responsive Design** - Works on desktop and mobile devices

## 🛠 Setup

### Prerequisites

- Python 3.8+
- Access to the Shitpost Alpha PostgreSQL database
- Environment variables configured

### Installation

1. **Navigate to the shitty_ui directory:**
   ```bash
   cd shitty_ui
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables:**
   The dashboard automatically uses the global Shitpost Alpha settings from `shit/config/shitpost_settings.py`.
   Ensure your `DATABASE_URL` is set in your main project's `.env` file or environment variables.

4. **Run the dashboard:**
   ```bash
   python app.py
   ```

5. **Open your browser:**
   Visit `http://localhost:8050` to see the dashboard

## 🎛 Dashboard Components

### 📊 Statistics Cards
- **Total Posts** - Number of posts in the database
- **Analyzed Posts** - Posts with LLM predictions
- **High Confidence** - Predictions with confidence ≥ 0.7
- **Average Confidence** - Mean confidence score

### 🔍 Filter Controls
- **Has Prediction** - Show all posts, predictions only, or raw posts only
- **Assets** - Multi-select dropdown of all mentioned assets
- **Confidence Range** - Slider to filter by confidence scores
- **Date Range** - Date picker for temporal filtering
- **Posts to Show** - Limit number of displayed posts

### 📋 Posts Table
- **Timestamp** - When the post was made
- **Post Text** - Full content of the Truth Social post
- **Assets** - List of implicated assets
- **Sentiment** - Bullish/bearish market impact
- **Confidence** - LLM confidence score (0.0-1.0)
- **Thesis** - Detailed investment thesis from LLM
- **Status** - Analysis status (completed/bypassed/error)
- **Comment** - Bypass reason or additional notes

### 📈 Analytics Charts
- **Sentiment Distribution** - Pie chart showing bullish/bearish breakdown
- **Confidence Distribution** - Histogram of confidence scores

## 🚀 Deployment on Railway

The dashboard is designed for easy deployment on Railway:

1. **Add as new service** in your Railway project
2. **Point to shitty_ui directory**
3. **Set environment variables:**
   - `DATABASE_URL` - Your Neon PostgreSQL connection string
4. **Deploy** - Railway will auto-detect Python and install dependencies

The dashboard will be available at `https://<service-name>.up.railway.app`

## 🎨 Theming

The dashboard uses an obnoxiously American theme with:
- **Colors**: Red (#B22234), White (#FFFFFF), Blue (#3C3B6E)
- **Icons**: Font Awesome icons with patriotic flair
- **Typography**: Bold, attention-grabbing fonts
- **Language**: Over-the-top American patriotism and trading terminology

## 🔧 Technical Details

### Architecture
- **Frontend**: Plotly Dash with Bootstrap components
- **Backend**: Async SQLAlchemy with PostgreSQL
- **Data Source**: Shitpost Alpha database (truth_social_shitposts + predictions tables)
- **Refresh Rate**: 5 minutes (matches pipeline schedule)

### Key Files
- `app.py` - Main entry point and server configuration
- `layout.py` - Dashboard layout, components, and callbacks
- `data.py` - Database connection and query functions
- `requirements.txt` - Python dependencies

### Database Queries
The dashboard uses optimized async queries to:
- Load recent posts with predictions
- Filter by various criteria
- Get available assets for dropdown
- Calculate summary statistics

## 🐛 Troubleshooting

### Common Issues

1. **Database Connection Error**
   - Verify `DATABASE_URL` is set in your main project's `.env` file or environment variables
   - Check database credentials and network access
   - Ensure the dashboard can import `shit.config.shitpost_settings`

2. **No Data Showing**
   - Ensure the database has posts and predictions
   - Check filter settings (might be too restrictive)

3. **Charts Not Loading**
   - Verify data is available for the selected filters
   - Check browser console for JavaScript errors

### Debug Mode
Run with debug enabled for development:
```bash
python app.py --debug
```

## 📞 Support

For issues with the Shitty UI dashboard:
- Check the main [Shitpost Alpha README](../README.md)
- Review the [CHANGELOG](../CHANGELOG.md) for recent updates
- Contact: [christophertrogers37@gmail.com](mailto:christophertrogers37@gmail.com)

## 🇺🇸 Making America Trade Again! 🇺🇸

*"In America, we don't just trade stocks - we trade FREEDOM!"* 🚀📈
