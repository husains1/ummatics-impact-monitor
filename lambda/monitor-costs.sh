#!/bin/bash
# Monitor Lambda costs and usage

echo "╔════════════════════════════════════════════════════════════╗"
echo "║  Lambda Sentiment Analysis - Cost & Usage Monitor         ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

FUNCTION_NAME="ummatics-sentiment-analysis"
DAYS_AGO=${1:-30}

START_TIME=$(date -u -d "$DAYS_AGO days ago" +%Y-%m-%dT%H:%M:%S)Z
END_TIME=$(date -u +%Y-%m-%dT%H:%M:%S)Z

echo "Monitoring period: Last $DAYS_AGO days"
echo "From: $START_TIME"
echo "To:   $END_TIME"
echo ""

# Check if function exists
if ! aws lambda get-function --function-name $FUNCTION_NAME &> /dev/null; then
    echo "❌ Lambda function '$FUNCTION_NAME' not found"
    echo "   Deploy it first: cd lambda && ./deploy.sh"
    exit 1
fi

echo "✓ Lambda function found"
echo ""

# Get invocations
echo "📊 Invocations:"
aws cloudwatch get-metric-statistics \
    --namespace AWS/Lambda \
    --metric-name Invocations \
    --dimensions Name=FunctionName,Value=$FUNCTION_NAME \
    --start-time $START_TIME \
    --end-time $END_TIME \
    --period 86400 \
    --statistics Sum \
    --query 'Datapoints[*].[Timestamp,Sum]' \
    --output table

# Get errors
echo ""
echo "❌ Errors:"
aws cloudwatch get-metric-statistics \
    --namespace AWS/Lambda \
    --metric-name Errors \
    --dimensions Name=FunctionName,Value=$FUNCTION_NAME \
    --start-time $START_TIME \
    --end-time $END_TIME \
    --period 86400 \
    --statistics Sum \
    --query 'Datapoints[*].[Timestamp,Sum]' \
    --output table

# Get duration
echo ""
echo "⏱️  Average Duration (ms):"
aws cloudwatch get-metric-statistics \
    --namespace AWS/Lambda \
    --metric-name Duration \
    --dimensions Name=FunctionName,Value=$FUNCTION_NAME \
    --start-time $START_TIME \
    --end-time $END_TIME \
    --period 86400 \
    --statistics Average \
    --query 'Datapoints[*].[Timestamp,Average]' \
    --output table

# Calculate estimated cost
echo ""
echo "💰 Estimated Cost:"
echo ""

# Get total invocations
TOTAL_INVOCATIONS=$(aws cloudwatch get-metric-statistics \
    --namespace AWS/Lambda \
    --metric-name Invocations \
    --dimensions Name=FunctionName,Value=$FUNCTION_NAME \
    --start-time $START_TIME \
    --end-time $END_TIME \
    --period $((DAYS_AGO * 86400)) \
    --statistics Sum \
    --query 'Datapoints[0].Sum' \
    --output text)

if [ "$TOTAL_INVOCATIONS" = "None" ] || [ -z "$TOTAL_INVOCATIONS" ]; then
    TOTAL_INVOCATIONS=0
fi

# Get average duration
AVG_DURATION=$(aws cloudwatch get-metric-statistics \
    --namespace AWS/Lambda \
    --metric-name Duration \
    --dimensions Name=FunctionName,Value=$FUNCTION_NAME \
    --start-time $START_TIME \
    --end-time $END_TIME \
    --period $((DAYS_AGO * 86400)) \
    --statistics Average \
    --query 'Datapoints[0].Average' \
    --output text)

if [ "$AVG_DURATION" = "None" ] || [ -z "$AVG_DURATION" ]; then
    AVG_DURATION=0
fi

# Lambda pricing (as of 2025)
# Memory: 2048MB = 2GB
# Request cost: $0.20 per 1M requests = $0.0000002 per request
# Compute cost: $0.0000166667 per GB-second

MEMORY_GB=2
REQUEST_COST_PER_MILLION=0.20
COMPUTE_COST_PER_GB_SECOND=0.0000166667

# Calculate costs
REQUEST_COST=$(echo "scale=6; $TOTAL_INVOCATIONS * $REQUEST_COST_PER_MILLION / 1000000" | bc)
DURATION_SECONDS=$(echo "scale=2; $AVG_DURATION / 1000" | bc)
GB_SECONDS=$(echo "scale=2; $TOTAL_INVOCATIONS * $DURATION_SECONDS * $MEMORY_GB" | bc)
COMPUTE_COST=$(echo "scale=6; $GB_SECONDS * $COMPUTE_COST_PER_GB_SECOND" | bc)
TOTAL_COST=$(echo "scale=6; $REQUEST_COST + $COMPUTE_COST" | bc)

echo "Total Invocations: $TOTAL_INVOCATIONS"
echo "Avg Duration:      ${AVG_DURATION} ms (${DURATION_SECONDS}s)"
echo "GB-seconds:        $GB_SECONDS"
echo ""
echo "Request Cost:      \$$REQUEST_COST"
echo "Compute Cost:      \$$COMPUTE_COST"
echo "─────────────────────────────────"
echo "Total Cost:        \$$TOTAL_COST"
echo ""

# Free tier check
FREE_TIER_REQUESTS=1000000
FREE_TIER_GB_SECONDS=400000

if (( $(echo "$TOTAL_INVOCATIONS < $FREE_TIER_REQUESTS" | bc -l) )); then
    echo "✅ Within free tier for requests ($TOTAL_INVOCATIONS / $FREE_TIER_REQUESTS)"
else
    echo "⚠️  Exceeded free tier for requests!"
fi

if (( $(echo "$GB_SECONDS < $FREE_TIER_GB_SECONDS" | bc -l) )); then
    echo "✅ Within free tier for compute ($GB_SECONDS / $FREE_TIER_GB_SECONDS GB-s)"
else
    echo "⚠️  Exceeded free tier for compute!"
fi

echo ""
echo "💡 Free tier covers:"
echo "   - 1M requests/month"
echo "   - 400,000 GB-seconds/month"
echo "   - Valid for first 12 months"
echo ""

# Monthly projection
MONTHLY_INVOCATIONS=$(echo "scale=0; $TOTAL_INVOCATIONS * 30 / $DAYS_AGO" | bc)
MONTHLY_GB_SECONDS=$(echo "scale=2; $GB_SECONDS * 30 / $DAYS_AGO" | bc)
MONTHLY_COST=$(echo "scale=6; $TOTAL_COST * 30 / $DAYS_AGO" | bc)

echo "📈 Monthly Projection (based on last $DAYS_AGO days):"
echo "   Invocations:  $MONTHLY_INVOCATIONS/month"
echo "   GB-seconds:   $MONTHLY_GB_SECONDS/month"
echo "   Cost:         \$$MONTHLY_COST/month"
echo ""

if (( $(echo "$MONTHLY_COST < 0.01" | bc -l) )); then
    echo "✅ Excellent! Costs are negligible (<$0.01/month)"
elif (( $(echo "$MONTHLY_COST < 1" | bc -l) )); then
    echo "✅ Great! Costs are very low (<$1/month)"
else
    echo "⚠️  Consider optimizing (>$1/month)"
    echo "   - Increase batch size to reduce invocations"
    echo "   - Check for unnecessary invocations"
fi

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                    Monitoring Complete                     ║"
echo "╚════════════════════════════════════════════════════════════╝"
