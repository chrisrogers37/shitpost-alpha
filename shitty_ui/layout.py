"""
Dashboard layout and callbacks for Shitty UI
Obnoxiously American-themed dashboard for Shitpost Alpha.
"""

import asyncio
from datetime import datetime, timedelta
from dash import Dash, html, dcc, dash_table, Input, Output, State, callback_context
import pandas as pd
from data import load_recent_posts, load_filtered_posts, get_available_assets, get_prediction_stats

def create_app() -> Dash:
    """Create and configure the Dash app."""
    
    app = Dash(__name__, external_stylesheets=[
        'https://codepen.io/chriddyp/pen/bWLwgP.css',
        'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css'
    ])
    
    # Set the title
    app.title = "🇺🇸 Shitpost Alpha - MURICA'S PREMIER TRADING DASHBOARD 🇺🇸"
    
    # Main layout
    app.layout = html.Div([
        # Header with obnoxiously American styling
        html.Div([
            html.H1([
                html.I(className="fas fa-flag-usa", style={"color": "#B22234", "margin-right": "10px"}),
                "SHITPOST ALPHA",
                html.I(className="fas fa-eagle", style={"color": "#3C3B6E", "margin-left": "10px"})
            ], style={
                "text-align": "center",
                "color": "#B22234",
                "font-size": "3em",
                "font-weight": "bold",
                "text-shadow": "2px 2px 4px #000000",
                "background": "linear-gradient(45deg, #B22234, #FFFFFF, #3C3B6E)",
                "background-clip": "text",
                "margin": "20px 0",
                "font-family": "Arial Black, sans-serif"
            }),
            html.P([
                "🇺🇸 AMERICA'S #1 AUTOMATED SHITPOST TRADING SIGNAL GENERATOR 🇺🇸",
                html.Br(),
                "Powered exclusively by the Shitposts of the Commander-in-Chief's (and OpenAI)",
                html.Br(),
                "This is the Shitty UI, not the Shitpost Alpha Dashboard. More to come.",
                html.Br(),
                html.Small("Making America Rich Again, Maybe* 🚀📈")
            ], style={
                "text-align": "center",
                "color": "#3C3B6E",
                "font-size": "1.2em",
                "font-weight": "bold",
                "margin-bottom": "10px"
            }),
            
        ]),
        
        # Auto-refresh interval
        dcc.Interval(
            id="refresh-interval",
            interval=5*60*1000,  # 5 minutes
            n_intervals=0
        ),
        
        # Filter controls
        html.Div([
            html.H3([
                html.I(className="fas fa-filter", style={"margin-right": "10px"}),
                "FILTER SHITPOSTS!"
            ], style={"color": "#B22234", "font-weight": "bold"}),
            
            html.Div([
                # Has Prediction filter
                html.Div([
                    html.Label("Has Prediction:", style={"font-weight": "bold", "margin-right": "10px"}),
                    dcc.Dropdown(
                        id="has-prediction-filter",
                        options=[
                            {"label": "🇺🇸 ALL POSTS (MURICA!)", "value": "all"},
                            {"label": "🎯 PREDICTIONS ONLY", "value": "true"},
                            {"label": "📝 RAW POSTS ONLY", "value": "false"}
                        ],
                        value="all",
                        style={"width": "200px"}
                    )
                ], style={"display": "inline-block", "margin-right": "20px"}),
                
                # Assets filter
                html.Div([
                    html.Label("Assets:", style={"font-weight": "bold", "margin-right": "10px"}),
                    dcc.Dropdown(
                        id="assets-filter",
                        multi=True,
                        placeholder="Select assets to filter...",
                        style={"width": "250px"}
                    )
                ], style={"display": "inline-block", "margin-right": "20px"}),
                
                # Confidence range
                html.Div([
                    html.Label("Confidence Range:", style={"font-weight": "bold", "margin-right": "10px"}),
                    dcc.RangeSlider(
                        id="confidence-slider",
                        min=0,
                        max=1,
                        step=0.05,
                        value=[0, 1],
                        marks={i/10: f"{i/10:.1f}" for i in range(0, 11)},
                        tooltip={"placement": "bottom", "always_visible": True}
                    )
                ], style={"display": "inline-block", "width": "300px", "margin-right": "20px"}),
                
                # Date range
                html.Div([
                    html.Label("Date Range:", style={"font-weight": "bold", "margin-right": "10px"}),
                    dcc.DatePickerRange(
                        id="date-range-picker",
                        start_date=(datetime.now() - timedelta(days=30)).date(),
                        end_date=datetime.now().date(),
                        display_format="YYYY-MM-DD"
                    )
                ], style={"display": "inline-block", "margin-right": "20px"}),
                
                # Limit selector
                html.Div([
                    html.Label("Posts to Show:", style={"font-weight": "bold", "margin-right": "10px"}),
                    dcc.Dropdown(
                        id="limit-selector",
                        options=[
                            {"label": "50", "value": 50},
                            {"label": "100", "value": 100},
                            {"label": "250", "value": 250},
                            {"label": "500", "value": 500}
                        ],
                        value=100,
                        style={"width": "100px"}
                    )
                ], style={"display": "inline-block"})
                
            ], style={"display": "flex", "align-items": "center", "flex-wrap": "wrap"})
            
        ], style={
            "border": "3px solid #B22234",
            "border-radius": "10px",
            "padding": "20px",
            "margin-bottom": "30px",
            "background": "linear-gradient(135deg, #FFFFFF, #F8F9FA)"
        }),
        
        # Main content area
        html.Div([
            # Posts table
            html.Div([
                html.H3([
                    html.I(className="fas fa-table", style={"margin-right": "10px"}),
                    "SHITPOST FEED - PRESIDENTIAL TRADING SIGNALS!"
                ], style={"color": "#B22234", "font-weight": "bold"}),
                
                dash_table.DataTable(
                    id="posts-table",
                    columns=[
                        {"name": "📅 Timestamp", "id": "timestamp", "type": "datetime"},
                        {"name": "📝 Post Text", "id": "text", "presentation": "markdown"},
                        {"name": "🎯 Assets", "id": "assets", "type": "text"},
                        {"name": "📈 Sentiment", "id": "market_impact", "type": "text"},
                        {"name": "🎲 Confidence", "id": "confidence", "type": "numeric", "format": {"specifier": ".2f"}},
                        {"name": "🧠 Thesis", "id": "thesis", "presentation": "markdown"},
                        {"name": "✅ Status", "id": "analysis_status", "type": "text"},
                        {"name": "💬 Comment", "id": "analysis_comment", "type": "text"}
                    ],
                    style_cell={
                        "textAlign": "left",
                        "fontFamily": "Arial, sans-serif",
                        "fontSize": "12px",
                        "whiteSpace": "normal",
                        "height": "auto",
                        "padding": "10px"
                    },
                    style_header={
                        "backgroundColor": "#B22234",
                        "color": "white",
                        "fontWeight": "bold",
                        "textAlign": "center"
                    },
                    style_data_conditional=[
                        {
                            "if": {"filter_query": "{market_impact} contains bullish"},
                            "backgroundColor": "#90EE90",
                            "color": "black"
                        },
                        {
                            "if": {"filter_query": "{market_impact} contains bearish"},
                            "backgroundColor": "#FFB6C1",
                            "color": "black"
                        }
                    ],
                    page_size=20,
                    sort_action="native",
                    filter_action="native",
                    style_table={"overflowX": "auto"}
                )
            ], style={"margin-bottom": "30px"}),
            
            # Statistics cards section
            html.Div([
                html.H3([
                    html.I(className="fas fa-chart-bar", style={"margin-right": "10px"}),
                    "SYSTEM KPIs - AMERICA'S METRICS! 📊"
                ], style={"color": "#B22234", "font-weight": "bold", "text-align": "center", "margin-bottom": "20px"}),
                
                html.Div(id="stats-cards", style={"margin-bottom": "30px"})
            ])
            
        ]),
        
        # Footer disclaimer
        html.Div([
            html.Hr(style={"border": "2px solid #B22234", "margin": "40px 0 20px 0"}),
            html.P([
                "* THIS IS VERY MUCH NOT FINANCIAL ADVICE AND VERY MUCH MORE FOR THE LOLS"
            ], style={
                "text-align": "center",
                "color": "#666666",
                "font-size": "0.9em",
                "font-style": "italic",
                "margin-bottom": "10px"
            }),
            html.P([
                html.I(className="fab fa-github", style={"margin-right": "8px"}),
                html.A(
                    "View Source Code on GitHub",
                    href="https://github.com/chrisrogers37/shitpost-alpha",
                    target="_blank",
                    style={
                        "color": "#3C3B6E",
                        "text-decoration": "none",
                        "font-weight": "bold"
                    }
                )
            ], style={
                "text-align": "center",
                "margin-bottom": "20px"
            })
        ])
        
    ], style={
        "background": "linear-gradient(135deg, #FFFFFF, #F8F9FA)",
        "min-height": "100vh",
        "padding": "20px",
        "font-family": "Arial, sans-serif"
    })
    
    return app

def register_callbacks(app: Dash):
    """Register all callbacks for the dashboard."""
    
    @app.callback(
        [Output("posts-table", "data"),
         Output("assets-filter", "options"),
         Output("stats-cards", "children")],
        [Input("refresh-interval", "n_intervals"),
         Input("has-prediction-filter", "value"),
         Input("assets-filter", "value"),
         Input("confidence-slider", "value"),
         Input("date-range-picker", "start_date"),
         Input("date-range-picker", "end_date"),
         Input("limit-selector", "value")]
    )
    def update_dashboard(n_intervals, has_prediction, selected_assets, confidence_range, 
                        start_date, end_date, limit):
        """Update dashboard data based on filters."""
        
        # Prepare filter parameters
        has_prediction_filter = None
        if has_prediction == "true":
            has_prediction_filter = True
        elif has_prediction == "false":
            has_prediction_filter = False
        
        # Load data with filters
        try:
            df = load_filtered_posts(
                limit=limit or 100,
                has_prediction=has_prediction_filter,
                assets_filter=selected_assets,
                confidence_min=confidence_range[0] if confidence_range else None,
                confidence_max=confidence_range[1] if confidence_range else None,
                date_from=start_date,
                date_to=end_date
            )
            
            # Get available assets for dropdown
            available_assets = get_available_assets()
            asset_options = [{"label": f"🇺🇸 {asset}", "value": asset} for asset in available_assets]
            
            # Get stats
            stats = get_prediction_stats()
            
        except Exception as e:
            print(f"Error loading data: {e}")
            df = pd.DataFrame()
            asset_options = []
            stats = {
                "total_posts": 0,
                "analyzed_posts": 0,
                "completed_analyses": 0,
                "bypassed_posts": 0,
                "avg_confidence": 0.0,
                "high_confidence_predictions": 0
            }
        
        # Prepare table data with proper formatting
        if not df.empty:
            # Create a copy and format the data for display
            df_display = df.copy()
            
            # Format timestamp as string
            df_display['timestamp'] = df_display['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
            
            # Format assets as comma-separated string
            df_display['assets'] = df_display['assets'].apply(
                lambda x: ', '.join(x) if isinstance(x, list) and x else 'None'
            )
            
            # Format market_impact as string
            df_display['market_impact'] = df_display['market_impact'].apply(
                lambda x: str(x) if x else 'None'
            )
            
            # Handle NaN confidence values
            df_display['confidence'] = df_display['confidence'].fillna(0.0)
            
            # Handle None values in other columns
            df_display['analysis_comment'] = df_display['analysis_comment'].fillna('')
            
            table_data = df_display.to_dict("records")
        else:
            table_data = []
        
        # Create stats cards
        stats_cards = create_stats_cards(stats)
        
        return table_data, asset_options, stats_cards


def create_stats_cards(stats: dict) -> html.Div:
    """Create statistics cards."""
    cards = []
    
    card_data = [
        ("Total Posts", stats.get("total_posts", 0), "fas fa-list", "#B22234"),
        ("Analyzed Posts", stats.get("analyzed_posts", 0), "fas fa-brain", "#3C3B6E"),
        ("High Confidence", stats.get("high_confidence_predictions", 0), "fas fa-star", "#FFD700"),
        ("Avg Confidence", f"{stats.get('avg_confidence', 0):.2f}", "fas fa-chart-line", "#228B22")
    ]
    
    for title, value, icon, color in card_data:
        card = html.Div([
            html.Div([
                html.I(className=icon, style={"font-size": "2em", "color": color}),
                html.H3(str(value), style={"margin": "10px 0", "color": color, "font-weight": "bold"}),
                html.P(title, style={"margin": 0, "font-size": "0.9em", "color": "#666"})
            ], style={
                "text-align": "center",
                "padding": "20px",
                "border": f"2px solid {color}",
                "border-radius": "10px",
                "background": "white",
                "box-shadow": "0 4px 6px rgba(0,0,0,0.1)"
            })
        ], style={"width": "25%", "display": "inline-block", "margin": "10px"})
        cards.append(card)
    
    return html.Div(cards, style={"display": "flex", "justify-content": "space-around", "flex-wrap": "wrap"})
