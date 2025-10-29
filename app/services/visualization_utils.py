"""
Visualization utilities for AI-generated reports
Generates chart descriptions and data visualizations with proper normalization and formatting
"""

from typing import Dict, Any, List, Tuple
import json
import math
from statistics import mean, stdev


# Impact category units and normalization factors
IMPACT_CATEGORIES_UNITS = {
    'ClimateChange': {'unit': 'kg CO₂-eq', 'factor': 1.0, 'category': 'climate'},
    'Global Warming': {'unit': 'kg CO₂-eq', 'factor': 1.0, 'category': 'climate'},
    'climate_change': {'unit': 'kg CO₂-eq', 'factor': 1.0, 'category': 'climate'},
    'Ozone Depletion': {'unit': 'kg CFC-11-eq', 'factor': 1000000.0, 'category': 'ozone'},
    'Acidification': {'unit': 'kg SO₂-eq', 'factor': 100.0, 'category': 'acidification'},
    'Eutrophication': {'unit': 'kg PO₄³⁻-eq', 'factor': 1000.0, 'category': 'eutrophication'},
    'Photochemical Ozone': {'unit': 'kg C₂H₄-eq', 'factor': 1000.0, 'category': 'smog'},
    'Land Use': {'unit': 'm² year', 'factor': 0.001, 'category': 'land'},
    'Water Use': {'unit': 'm³', 'factor': 0.01, 'category': 'water'},
    'Fossil Fuel Depletion': {'unit': 'MJ surplus', 'factor': 0.1, 'category': 'resources'},
    'Human Toxicity': {'unit': 'CTUh', 'factor': 1000000.0, 'category': 'toxicity'},
    'Freshwater Ecotoxicity': {'unit': 'CTUe', 'factor': 10000.0, 'category': 'toxicity'},
    'Marine Ecotoxicity': {'unit': 'CTUe', 'factor': 100000.0, 'category': 'toxicity'},
    'Terrestrial Ecotoxicity': {'unit': 'CTUe', 'factor': 1000.0, 'category': 'toxicity'},
    'Mineral Depletion': {'unit': 'kg Fe-eq', 'factor': 100.0, 'category': 'resources'},
}


def normalize_impact_data(impact_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Normalize impact category data for comparison visualization
    
    Args:
        impact_data: Dictionary of impact categories with values and units
        
    Returns:
        Dictionary with normalized values, original values, and metadata
    """
    normalized_data = {}
    
    for category, data in impact_data.items():
        if isinstance(data, dict):
            value = data.get('value', 0)
            unit = data.get('unit', '')
        else:
            value = data if data is not None else 0
            unit = 'units'
        
        # Get normalization info
        norm_info = IMPACT_CATEGORIES_UNITS.get(category, {
            'unit': unit, 
            'factor': 1.0, 
            'category': 'other'
        })
        
        # Normalize the value
        normalized_value = float(value) * norm_info['factor']
        
        # Format for display
        clean_name = category.replace('_', ' ').replace('Change', '').strip()
        
        normalized_data[category] = {
            'original_value': value,
            'normalized_value': normalized_value,
            'original_unit': unit,
            'display_unit': norm_info['unit'],
            'category_type': norm_info['category'],
            'display_name': clean_name,
            'significance': 'high' if normalized_value > 100 else 'medium' if normalized_value > 10 else 'low'
        }
    
    return normalized_data


def create_professional_color_palette() -> Dict[str, List[str]]:
    """Create professional color palette for different chart types"""
    return {
        'primary': ['#2563EB', '#059669', '#DC2626', '#D97706', '#7C2D12', '#9333EA'],
        'climate': ['#EF4444', '#DC2626', '#B91C1C', '#991B1B'],  # Red tones for climate
        'water': ['#3B82F6', '#2563EB', '#1D4ED8', '#1E40AF'],    # Blue tones for water
        'land': ['#10B981', '#059669', '#047857', '#065F46'],     # Green tones for land
        'resources': ['#F59E0B', '#D97706', '#B45309', '#92400E'], # Orange tones for resources
        'toxicity': ['#8B5CF6', '#7C3AED', '#6D28D9', '#5B21B6'], # Purple tones for toxicity
        'quality': ['#10B981', '#3B82F6', '#F59E0B', '#EF4444'],  # Green to red gradient
        'neutral': ['#6B7280', '#9CA3AF', '#D1D5DB', '#E5E7EB']
    }


def generate_impact_breakdown_chart(breakdown_data: Dict[str, Any]) -> str:
    """
    Generate professional pie chart for impact breakdown by crop/food with proper formatting
    """
    if not breakdown_data:
        return ""

    # Get total impacts per food item (using climate change as primary metric)
    food_impacts = {}
    total_impact = 0
    
    for food_name, impacts in breakdown_data.items():
        if isinstance(impacts, dict):
            # Try to get climate change impact
            for key in ['ClimateChange', 'climate_change', 'Global Warming']:
                if key in impacts:
                    impact = impacts[key]
                    if isinstance(impact, dict):
                        value = impact.get('value', 0)
                    else:
                        value = impact if impact is not None else 0
                    
                    food_impacts[food_name] = float(value)
                    total_impact += float(value)
                    break

    if not food_impacts or total_impact == 0:
        return ""

    # Sort by impact size (descending)
    sorted_impacts = sorted(food_impacts.items(), key=lambda x: x[1], reverse=True)

    # Generate professional Mermaid pie chart with percentages
    mermaid = "```mermaid\npie title Climate Impact Distribution by Crop (kg CO₂-eq)\n"
    
    colors = create_professional_color_palette()['primary']
    
    for i, (food, value) in enumerate(sorted_impacts):
        percentage = (value / total_impact) * 100
        # Clean food name and format value
        clean_name = food.replace('"', '').replace("'", "")[:25]  # Truncate long names
        mermaid += f'    "{clean_name} ({percentage:.1f}%)" : {value:.3f}\n'
    
    mermaid += "```\n"

    # Add summary table
    mermaid += f"\n**Total Climate Impact:** {total_impact:.3f} kg CO₂-eq\n\n"
    mermaid += "| Crop | Impact (kg CO₂-eq) | Percentage | Significance |\n"
    mermaid += "|------|-------------------|------------|-------------|\n"
    
    for food, value in sorted_impacts:
        percentage = (value / total_impact) * 100
        significance = "🔴 High" if percentage > 40 else "🟡 Medium" if percentage > 15 else "🟢 Low"
        mermaid += f"| {food} | {value:.3f} | {percentage:.1f}% | {significance} |\n"

    return mermaid


def generate_impact_categories_chart(midpoint_impacts: Dict[str, Any]) -> str:
    """
    Generate professional normalized bar chart for different impact categories
    """
    if not midpoint_impacts:
        return ""

    # Normalize impact data
    normalized_data = normalize_impact_data(midpoint_impacts)
    
    if not normalized_data:
        return ""

    # Sort by normalized value (descending)
    sorted_impacts = sorted(
        normalized_data.items(), 
        key=lambda x: x[1]['normalized_value'], 
        reverse=True
    )

    # Limit to top 8 most significant categories
    top_impacts = sorted_impacts[:8]
    
    # Create professional table format with proper units
    chart_content = "\n## Environmental Impact Categories Analysis\n\n"
    chart_content += "### Normalized Impact Comparison\n"
    chart_content += "*Values normalized for cross-category comparison*\n\n"
    
    chart_content += "| Category | Original Value | Unit | Normalized Score | Significance |\n"
    chart_content += "|----------|----------------|------|------------------|-------------|\n"
    
    for category, data in top_impacts:
        original_value = data['original_value']
        original_unit = data['original_unit'] or data['display_unit']
        normalized_value = data['normalized_value']
        significance = data['significance']
        display_name = data['display_name']
        
        # Format original value
        if isinstance(original_value, (int, float)) and original_value != 0:
            if original_value < 0.001:
                orig_display = f"{original_value:.2e}"
            elif original_value < 1:
                orig_display = f"{original_value:.4f}"
            elif original_value < 100:
                orig_display = f"{original_value:.2f}"
            else:
                orig_display = f"{original_value:.1f}"
        else:
            orig_display = "0.00"
        
        # Significance indicators
        significance_icon = {
            'high': '🔴 High',
            'medium': '🟡 Medium', 
            'low': '🟢 Low'
        }.get(significance, '⚪ Minimal')
        
        chart_content += f"| **{display_name}** | {orig_display} | {original_unit} | {normalized_value:.1f} | {significance_icon} |\n"
    
    # Add ASCII bar chart for visual comparison
    chart_content += "\n### Visual Impact Comparison\n"
    chart_content += "```\n"
    chart_content += f"{'Impact Category':<25} | {'Normalized Score':<15} | Bar\n"
    chart_content += f"{'-'*25} | {'-'*15} | {'-'*30}\n"
    
    # Calculate scale for ASCII bars
    max_norm_value = max([data['normalized_value'] for _, data in top_impacts])
    scale_factor = 30 / max_norm_value if max_norm_value > 0 else 1
    
    for category, data in top_impacts:
        display_name = data['display_name'][:24]  # Truncate long names
        normalized_value = data['normalized_value']
        bar_length = int(normalized_value * scale_factor)
        
        # Create colored bar based on significance
        if data['significance'] == 'high':
            bar_char = '█'  # Full block for high impact
        elif data['significance'] == 'medium':
            bar_char = '▓'  # Medium shade for medium impact
        else:
            bar_char = '▒'  # Light shade for low impact
            
        bar = bar_char * bar_length
        
        chart_content += f"{display_name:<25} | {normalized_value:>12.1f} | {bar}\n"
    
    chart_content += "```\n"
    
    # Add methodology note
    chart_content += "\n*Note: Values are normalized using standard LCA characterization factors to enable cross-category comparison.*\n"
    
    return chart_content


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


def generate_ascii_chart(data: Dict[str, float], title: str = "Impact Distribution", max_width: int = 40) -> str:
    """
    Generate professional ASCII bar chart with proper formatting and units
    """
    if not data:
        return ""

    # Check if data needs normalization (mixed units)
    needs_normalization = False
    if isinstance(list(data.values())[0], dict):
        # Data includes unit information
        units = set()
        for value_info in data.values():
            if isinstance(value_info, dict):
                units.add(value_info.get('unit', 'units'))
        needs_normalization = len(units) > 1

    # Process data
    processed_data = {}
    if needs_normalization and isinstance(list(data.values())[0], dict):
        # Normalize the data
        normalized = normalize_impact_data(data)
        for key, norm_data in normalized.items():
            processed_data[norm_data['display_name']] = {
                'value': norm_data['normalized_value'],
                'original_value': norm_data['original_value'],
                'unit': norm_data['original_unit'],
                'significance': norm_data['significance']
            }
        value_label = "Normalized Score"
    else:
        # Simple numeric data
        for key, value in data.items():
            if isinstance(value, dict):
                processed_data[key] = {
                    'value': value.get('value', 0),
                    'unit': value.get('unit', 'units'),
                    'significance': 'medium'
                }
            else:
                processed_data[key] = {
                    'value': float(value) if value is not None else 0,
                    'unit': 'units',
                    'significance': 'medium'
                }
        value_label = "Value"

    # Sort by value
    sorted_items = sorted(processed_data.items(), key=lambda x: x[1]['value'], reverse=True)
    
    if not sorted_items:
        return ""

    # Calculate scale
    max_value = max(item[1]['value'] for item in sorted_items)
    scale_factor = max_width / max_value if max_value > 0 else 1

    # Generate chart
    chart = f"\n### {title}\n\n"
    chart += "```\n"
    chart += f"{'Category':<25} | {value_label:<12} | {'Bar':<{max_width}} | Status\n"
    chart += f"{'-'*25} | {'-'*12} | {'-'*max_width} | {'-'*8}\n"

    for label, info in sorted_items[:10]:  # Limit to top 10
        value = info['value']
        significance = info['significance']
        
        # Create bar
        bar_length = int(value * scale_factor)
        
        # Choose bar character based on significance
        if significance == 'high':
            bar_char = '█'  # Full block
        elif significance == 'medium':
            bar_char = '▓'  # Medium shade
        else:
            bar_char = '▒'  # Light shade
            
        bar = bar_char * bar_length
        
        # Format value
        if value < 0.01:
            value_str = f"{value:.2e}"
        elif value < 1:
            value_str = f"{value:.3f}"
        elif value < 100:
            value_str = f"{value:.1f}"
        else:
            value_str = f"{value:.0f}"
        
        # Status indicator
        status_icon = {
            'high': '🔴',
            'medium': '🟡',
            'low': '🟢'
        }.get(significance, '⚪')
        
        # Truncate long labels
        display_label = label[:24]
        
        chart += f"{display_label:<25} | {value_str:>12} | {bar:<{max_width}} | {status_icon}\n"

    chart += "```\n"

    # Add summary statistics
    if len(sorted_items) > 1:
        values = [item[1]['value'] for item in sorted_items]
        chart += f"\n**Summary:** {len(sorted_items)} categories, "
        chart += f"Range: {min(values):.2f} - {max(values):.2f}"
        if needs_normalization:
            chart += " (normalized)"
        chart += "\n"

    return chart


def format_statistics_table(stats: Dict[str, Any]) -> str:
    """
    Format statistics into a professional markdown table with enhanced formatting
    """
    if not stats:
        return ""

    table = "\n## Key Performance Indicators\n\n"
    table += "| Metric | Value | Unit | Performance | Interpretation |\n"
    table += "|--------|-------|------|-------------|----------------|\n"

    for metric, data in stats.items():
        if isinstance(data, dict):
            value = data.get('value', 0)
            unit = data.get('unit', '')
            
            # Format value based on magnitude
            if isinstance(value, (int, float)) and value != 0:
                if abs(value) < 0.001:
                    value_display = f"{value:.2e}"
                elif abs(value) < 1:
                    value_display = f"{value:.4f}"
                elif abs(value) < 100:
                    value_display = f"{value:.2f}"
                else:
                    value_display = f"{value:.1f}"
            else:
                value_display = "0.00"
            
            # Determine performance level (rough heuristic)
            if isinstance(value, (int, float)):
                if 'climate' in metric.lower() or 'co2' in metric.lower():
                    # Lower is better for climate impact
                    if value < 1:
                        performance = "🟢 Excellent"
                    elif value < 5:
                        performance = "🟡 Good"
                    elif value < 15:
                        performance = "🟠 Average"
                    else:
                        performance = "🔴 High Impact"
                    
                    interpretation = "Lower values indicate better climate performance"
                elif 'quality' in metric.lower() or 'confidence' in metric.lower():
                    # Higher is better for quality metrics
                    if value > 0.8:
                        performance = "🟢 Excellent"
                    elif value > 0.6:
                        performance = "🟡 Good"
                    elif value > 0.4:
                        performance = "🟠 Fair"
                    else:
                        performance = "🔴 Poor"
                    
                    interpretation = "Higher values indicate better data quality"
                else:
                    # Generic assessment
                    performance = "📊 Measured"
                    interpretation = "Refer to benchmarking section for context"
            else:
                performance = "📊 Measured"
                interpretation = "Qualitative assessment"
            
            table += f"| **{metric}** | {value_display} | {unit} | {performance} | {interpretation} |\n"
        else:
            table += f"| **{metric}** | {data} | - | 📊 Measured | Qualitative metric |\n"

    # Add summary note
    table += "\n*Performance indicators use standard LCA benchmarks and industry best practices for agricultural systems in Africa.*\n"

    return table


def generate_all_visualizations(assessment_data: Dict[str, Any]) -> Dict[str, str]:
    """
    Generate all available visualizations for the assessment with professional formatting

    Returns:
        Dictionary of visualization type to visualization content
    """
    visualizations = {}

    # Impact breakdown chart
    breakdown = assessment_data.get('breakdown_by_food', {})
    if breakdown:
        visualizations['impact_breakdown'] = generate_impact_breakdown_chart(breakdown)
        visualizations['impact_flowchart'] = generate_impact_flowchart(breakdown)

    # Impact categories - enhanced with normalization
    midpoint = assessment_data.get('midpoint_impacts', {})
    if midpoint:
        visualizations['impact_categories'] = generate_impact_categories_chart(midpoint)
        # Enhanced ASCII chart with normalization
        visualizations['impact_ascii'] = generate_ascii_chart(midpoint, "Environmental Impact Categories (Normalized)")

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

    # Enhanced statistics table with performance indicators
    stats = {}
    single_score = assessment_data.get('single_score', {})
    if isinstance(single_score, dict):
        stats['Overall Environmental Impact Score'] = single_score

    endpoint = assessment_data.get('endpoint_impacts', {})
    if endpoint:
        # Add endpoint impacts with better labeling
        for key, value in endpoint.items():
            clean_key = key.replace('_', ' ').title()
            stats[f"Endpoint Impact - {clean_key}"] = value

    # Add key midpoint impacts to stats
    if midpoint:
        # Add the most significant categories
        normalized_midpoint = normalize_impact_data(midpoint)
        top_impacts = sorted(
            normalized_midpoint.items(), 
            key=lambda x: x[1]['normalized_value'], 
            reverse=True
        )[:3]  # Top 3 most significant impacts
        
        for category, data in top_impacts:
            if data['significance'] in ['high', 'medium']:
                stats[f"{data['display_name']} Impact"] = {
                    'value': data['original_value'],
                    'unit': data['original_unit']
                }

    # Add data quality metrics to stats
    if data_quality:
        if 'overall_confidence' in data_quality:
            stats['Data Quality Confidence'] = {
                'value': data_quality['overall_confidence'],
                'unit': 'level'
            }
        if 'completeness_score' in data_quality:
            stats['Data Completeness'] = {
                'value': data_quality['completeness_score'],
                'unit': 'score (0-1)'
            }

    if stats:
        visualizations['statistics_table'] = format_statistics_table(stats)

    # Add summary insights
    visualizations['summary_insights'] = generate_summary_insights(assessment_data)

    return visualizations


def generate_summary_insights(assessment_data: Dict[str, Any]) -> str:
    """
    Generate key insights summary from the assessment data
    """
    insights = "\n## Key Assessment Insights\n\n"
    
    # Analyze midpoint impacts
    midpoint = assessment_data.get('midpoint_impacts', {})
    if midpoint:
        normalized_data = normalize_impact_data(midpoint)
        high_impact_categories = [
            data['display_name'] for _, data in normalized_data.items() 
            if data['significance'] == 'high'
        ]
        
        if high_impact_categories:
            insights += f"🔴 **High Impact Areas:** {', '.join(high_impact_categories[:3])}\n"
        
        # Find dominant impact
        if normalized_data:
            top_impact = max(normalized_data.items(), key=lambda x: x[1]['normalized_value'])
            insights += f"📊 **Dominant Impact:** {top_impact[1]['display_name']} contributes most significantly to environmental burden\n"
    
    # Analyze data quality
    data_quality = assessment_data.get('data_quality', {})
    if data_quality:
        confidence = data_quality.get('overall_confidence', 'Medium')
        completeness = data_quality.get('completeness_score', 0.5)
        
        if completeness > 0.8:
            insights += "✅ **Data Quality:** Excellent - High confidence in results\n"
        elif completeness > 0.6:
            insights += "⚠️ **Data Quality:** Good - Results are reliable with minor gaps\n"
        else:
            insights += "🚨 **Data Quality:** Limited - Results should be interpreted cautiously\n"
    
    # Analyze recommendations
    recommendations = assessment_data.get('recommendations', [])
    if recommendations:
        high_priority = len([r for r in recommendations if r.get('priority', '').lower() == 'high'])
        if high_priority > 0:
            insights += f"⚡ **Action Required:** {high_priority} high-priority recommendations identified\n"
    
    # Farm-specific insights
    breakdown = assessment_data.get('breakdown_by_food', {})
    if breakdown and len(breakdown) > 1:
        # Find the crop with highest climate impact
        crop_impacts = {}
        for crop, impacts in breakdown.items():
            climate_impact = impacts.get('ClimateChange', impacts.get('climate_change', {}))
            if isinstance(climate_impact, dict):
                crop_impacts[crop] = climate_impact.get('value', 0)
        
        if crop_impacts:
            highest_impact_crop = max(crop_impacts.items(), key=lambda x: x[1])
            total_impact = sum(crop_impacts.values())
            percentage = (highest_impact_crop[1] / total_impact * 100) if total_impact > 0 else 0
            
            if percentage > 50:
                insights += f"🌾 **Crop Focus:** {highest_impact_crop[0]} accounts for {percentage:.0f}% of climate impact\n"
    
    insights += f"\n*Assessment completed with {len(midpoint)} impact categories analyzed*\n"
    
    return insights
