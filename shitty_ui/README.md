# Shitpost Alpha - Prediction Performance Dashboard

**Focus on what matters: How well are our predictions performing?**

## Overview

The redesigned Shitpost Alpha dashboard shifts focus from raw data display to actionable prediction performance insights. Instead of a table-first approach, the dashboard now leads with key metrics, performance charts, and the ability to drill down into similar historical predictions.

## Key Features

- **Performance Metrics** - Accuracy rate, total P&L, average return at a glance
- **Accuracy by Confidence** - See how high-confidence vs low-confidence predictions perform
- **Performance by Asset** - Which assets are we best at predicting?
- **Recent Signals** - Latest predictions with their outcomes (correct/incorrect/pending)
- **Asset Deep Dive** - Select any asset to see all historical predictions and their results
- **Collapsible Data Table** - Full data still available, but not the primary focus
- **Dark Theme** - Professional, clean design inspired by modern trading platforms

## Setup

### Prerequisites

- Python 3.8+
- Access to the Shitpost Alpha PostgreSQL database
- Market data and prediction outcomes populated

### Installation

1. **Install dependencies** (from project root):
   ```bash
   pip install -r requirements.txt
   ```

2. **Ensure environment variables are set:**
   The dashboard uses settings from `shit/config/shitpost_settings.py`.
   Make sure `DATABASE_URL` is set in your `.env` file.

3. **Run the dashboard:**
   ```bash
   cd shitty_ui && python app.py
   ```

4. **Open your browser:**
   Visit `http://localhost:8050`

## Dashboard Components

### Performance Metrics Row
- **Prediction Accuracy** - Overall accuracy rate (7-day outcomes)
- **Total P&L** - Simulated profit/loss based on $1,000 positions
- **Avg Return** - Average 7-day return across predictions
- **Predictions Evaluated** - Count of predictions with outcome data

### Accuracy by Confidence Chart
Bar chart showing how accuracy varies by confidence level:
- Low (<60%): Typically lower accuracy
- Medium (60-75%): Moderate accuracy
- High (>75%): Should have highest accuracy if model is well-calibrated

### Performance by Asset Chart
Bar chart showing accuracy for each asset ticker, helping identify:
- Which assets we predict well
- Which assets have poor track records

### Recent Signals
List of recent predictions with:
- Tweet preview
- Sentiment (bullish/bearish)
- Confidence score
- Outcome (Correct/Incorrect/Pending)
- Actual return if available

### Asset Deep Dive
Select any asset from the dropdown to see:
- Overall accuracy for that asset
- Average return and total P&L
- Timeline of all historical predictions with outcomes
- The actual tweet text for context

### Full Data Table (Collapsible)
Click to expand the traditional data table with:
- All predictions
- Filtering by confidence and date
- Sortable columns

## Deployment on Railway

The dashboard is designed for easy deployment on Railway:

1. **Add as new service** in your Railway project
2. **Point to shitty_ui directory**
3. **Set environment variables:**
   - `DATABASE_URL` - Your Neon PostgreSQL connection string
4. **Deploy** - Railway will auto-detect Python and install dependencies

The dashboard will be available at `https://<service-name>.up.railway.app`

## Technical Details

### Architecture
- **Frontend**: Plotly Dash with Bootstrap components (dark theme)
- **Backend**: Synchronous SQLAlchemy with PostgreSQL
- **Data Source**:
  - `truth_social_shitposts` - Posts table
  - `predictions` - LLM analysis results
  - `prediction_outcomes` - Validated outcomes with returns
- **Refresh Rate**: 5 minutes (auto-refresh)

### Key Files
- `app.py` - Main entry point and server configuration
- `layout.py` - Dashboard layout, components, and callbacks
- `data.py` - Database connection and query functions

### Database Queries
The dashboard queries:
- `get_performance_metrics()` - Overall accuracy and P&L
- `get_accuracy_by_confidence()` - Breakdown by confidence level
- `get_accuracy_by_asset()` - Breakdown by ticker
- `get_recent_signals()` - Recent predictions with outcomes
- `get_similar_predictions()` - Historical predictions for a specific asset
- `get_predictions_with_outcomes()` - Full data for the table

## Troubleshooting

### Common Issues

1. **Database Connection Error**
   - Verify `DATABASE_URL` is set in `.env`
   - Check database credentials and network access

2. **No Performance Data Showing**
   - Ensure you have run the market data backfill:
     ```bash
     python shit/market_data/backfill_prices.py
     python -m shit.market_data calculate-outcomes --days 365
     ```
   - The `prediction_outcomes` table must have data

3. **Charts Empty**
   - Verify `prediction_outcomes` table has records with `correct_t7` populated
   - Check that market prices have been backfilled

### Debug Mode
Run with debug enabled for development:
```bash
cd shitty_ui && python app.py --debug
```

## Support

For issues:
- Check the main [README](../README.md)
- Review the [ROADMAP](../documentation/ROADMAP.md) for planned features
- Review the [Market Data Architecture](../documentation/MARKET_DATA_ARCHITECTURE.md) for data setup
