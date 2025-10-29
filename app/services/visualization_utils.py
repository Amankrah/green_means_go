"""
Visualization utilities for AI-generated reports
Generates chart descriptions and data visualizations in Mermaid format
"""

from typing import Dict, Any, List
import json


def generate_impact_breakdown_chart(breakdown_data: Dict[str, Any]) -> str:
    """
    Generate Mermaid pie chart for impact breakdown by crop/food
    """
    if not breakdown_data:
        return ""

    # Get total impacts per food item (using climate change as primary metric)
    food_impacts = {}
    for food_name, impacts in breakdown_data.items():
        if isinstance(impacts, dict):
            # Try to get climate change impact
            for key in ['ClimateChange', 'climate_change', 'Global Warming']:
                if key in impacts:
                    impact = impacts[key]
                    if isinstance(impact, dict):
                        food_impacts[food_name] = impact.get('value', 0)
                    else:
                        food_impacts[food_name] = impact
                    break

    if not food_impacts:
        return ""

    # Generate Mermaid pie chart
    mermaid = "```mermaid\npie title Impact Breakdown by Crop/Food Product\n"
    for food, value in food_impacts.items():
        mermaid += f'    "{food}" : {value:.2f}\n'
    mermaid += "```\n"

    return mermaid


def generate_impact_categories_chart(midpoint_impacts: Dict[str, Any]) -> str:
    """
    Generate Mermaid bar chart for different impact categories
    """
    if not midpoint_impacts:
        return ""

    # Extract impact values
    impacts = {}
    for category, impact in midpoint_impacts.items():
        if isinstance(impact, dict):
            impacts[category] = impact.get('value', 0)
        else:
            impacts[category] = impact

    # Sort by value
    sorted_impacts = sorted(impacts.items(), key=lambda x: x[1], reverse=True)

    # Generate Mermaid bar chart (using gantt as approximation)
    mermaid = "```mermaid\ngraph TB\n"
    mermaid += "    subgraph Environmental Impact Categories\n"
    for i, (category, value) in enumerate(sorted_impacts[:6]):  # Top 6 categories
        clean_name = category.replace(' ', '_').replace('-', '_')
        mermaid += f"    {clean_name}[{category}<br/>{value:.4f}]\n"
    mermaid += "    end\n"
    mermaid += "```\n"

    return mermaid


def generate_benchmarking_chart(benchmarking_data: Dict[str, Any]) -> str:
    """
    Generate comparison chart for benchmarking
    """
    if not benchmarking_data:
        return ""

    comparisons = benchmarking_data.get('farm_type_comparison', {})
    if not comparisons:
        return ""

    mermaid = "```mermaid\ngraph LR\n"
    mermaid += "    A[Your Farm] --> B{Performance}\n"

    for farm_type, score in list(comparisons.items())[:4]:
        clean_name = farm_type.replace(' ', '_')
        mermaid += f"    B --> {clean_name}[{farm_type}: {score:.2f}]\n"

    mermaid += "```\n"

    return mermaid


def generate_recommendation_priority_chart(recommendations: List[Dict[str, Any]]) -> str:
    """
    Generate flowchart for recommendations by priority
    """
    if not recommendations:
        return ""

    high_priority = [r for r in recommendations if r.get('priority', '').lower() == 'high']
    medium_priority = [r for r in recommendations if r.get('priority', '').lower() == 'medium']
    low_priority = [r for r in recommendations if r.get('priority', '').lower() == 'low']

    mermaid = "```mermaid\ngraph TD\n"
    mermaid += "    Start[Start Implementation] --> Priority{Priority Level}\n"

    if high_priority:
        mermaid += "    Priority -->|High| High[High Priority Actions]\n"
        for i, rec in enumerate(high_priority[:3]):
            mermaid += f"    High --> H{i}[{rec.get('title', 'Action')[:30]}]\n"

    if medium_priority:
        mermaid += "    Priority -->|Medium| Medium[Medium Priority Actions]\n"
        for i, rec in enumerate(medium_priority[:3]):
            mermaid += f"    Medium --> M{i}[{rec.get('title', 'Action')[:30]}]\n"

    if low_priority:
        mermaid += "    Priority -->|Low| Low[Low Priority Actions]\n"

    mermaid += "```\n"

    return mermaid


def generate_data_quality_visualization(data_quality: Dict[str, Any]) -> str:
    """
    Generate radar chart for data quality metrics
    """
    if not isinstance(data_quality, dict):
        return ""

    metrics = {
        "Completeness": data_quality.get('completeness_score', 0) * 100,
        "Temporal": data_quality.get('temporal_representativeness', 0) * 100,
        "Geographical": data_quality.get('geographical_representativeness', 0) * 100,
        "Technological": data_quality.get('technological_representativeness', 0) * 100
    }

    # Generate a simple table representation
    table = "\n### Data Quality Scores\n\n"
    table += "| Metric | Score | Status |\n"
    table += "|--------|-------|--------|\n"

    for metric, score in metrics.items():
        status = "✅ Excellent" if score >= 80 else "⚠️ Good" if score >= 60 else "❌ Needs Improvement"
        table += f"| {metric} | {score:.1f}% | {status} |\n"

    return table


def generate_impact_flowchart(breakdown_data: Dict[str, Any]) -> str:
    """
    Generate a flowchart showing impact flow from inputs to outputs
    """
    if not breakdown_data:
        return ""

    mermaid = "```mermaid\ngraph LR\n"
    mermaid += "    Input[Farm Inputs] --> Process[Agricultural Production]\n"
    mermaid += "    Process --> Impacts{Environmental Impacts}\n"

    # Add major impact categories
    mermaid += "    Impacts --> GHG[GHG Emissions]\n"
    mermaid += "    Impacts --> Water[Water Use]\n"
    mermaid += "    Impacts --> Land[Land Use]\n"
    mermaid += "    Impacts --> Bio[Biodiversity]\n"

    mermaid += "    GHG --> Climate[Climate Impact]\n"
    mermaid += "    Water --> Resources[Resource Depletion]\n"
    mermaid += "    Land --> Habitat[Habitat Change]\n"
    mermaid += "    Bio --> Ecosystem[Ecosystem Health]\n"

    mermaid += "```\n"

    return mermaid


def generate_ascii_chart(data: Dict[str, float], title: str = "Impact Distribution", max_width: int = 50) -> str:
    """
    Generate simple ASCII bar chart for text reports
    """
    if not data:
        return ""

    # Normalize values
    max_value = max(data.values()) if data.values() else 1

    chart = f"\n### {title}\n\n```\n"

    for label, value in sorted(data.items(), key=lambda x: x[1], reverse=True):
        bar_length = int((value / max_value) * max_width)
        bar = "█" * bar_length
        chart += f"{label:30s} | {bar} {value:.2f}\n"

    chart += "```\n"

    return chart


def format_statistics_table(stats: Dict[str, Any]) -> str:
    """
    Format statistics into a professional markdown table
    """
    if not stats:
        return ""

    table = "\n| Metric | Value | Unit |\n"
    table += "|--------|-------|------|\n"

    for metric, data in stats.items():
        if isinstance(data, dict):
            value = data.get('value', 'N/A')
            unit = data.get('unit', '')
            if isinstance(value, (int, float)):
                table += f"| {metric} | {value:.4f} | {unit} |\n"
            else:
                table += f"| {metric} | {value} | {unit} |\n"
        else:
            table += f"| {metric} | {data} | - |\n"

    return table


def generate_all_visualizations(assessment_data: Dict[str, Any]) -> Dict[str, str]:
    """
    Generate all available visualizations for the assessment

    Returns:
        Dictionary of visualization type to visualization content
    """
    visualizations = {}

    # Impact breakdown chart
    breakdown = assessment_data.get('breakdown_by_food', {})
    if breakdown:
        visualizations['impact_breakdown'] = generate_impact_breakdown_chart(breakdown)
        visualizations['impact_flowchart'] = generate_impact_flowchart(breakdown)

    # Impact categories
    midpoint = assessment_data.get('midpoint_impacts', {})
    if midpoint:
        visualizations['impact_categories'] = generate_impact_categories_chart(midpoint)

        # ASCII chart for text version
        impact_values = {}
        for cat, imp in midpoint.items():
            if isinstance(imp, dict):
                impact_values[cat] = imp.get('value', 0)
        visualizations['impact_ascii'] = generate_ascii_chart(impact_values, "Impact Categories")

    # Benchmarking
    benchmarking = assessment_data.get('benchmarking', {})
    if benchmarking:
        visualizations['benchmarking'] = generate_benchmarking_chart(benchmarking)

    # Recommendations
    recommendations = assessment_data.get('recommendations', [])
    if recommendations:
        visualizations['recommendations_flow'] = generate_recommendation_priority_chart(recommendations)

    # Data quality
    data_quality = assessment_data.get('data_quality', {})
    if data_quality:
        visualizations['data_quality'] = generate_data_quality_visualization(data_quality)

    # Statistics table
    stats = {}
    single_score = assessment_data.get('single_score', {})
    if isinstance(single_score, dict):
        stats['Overall Impact Score'] = single_score

    endpoint = assessment_data.get('endpoint_impacts', {})
    if endpoint:
        stats.update(endpoint)

    if stats:
        visualizations['statistics_table'] = format_statistics_table(stats)

    return visualizations
