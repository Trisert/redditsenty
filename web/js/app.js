// Reddit Sentiment Analysis Dashboard
// With FTS5 full-text search

const API_BASE_URL = 'http://localhost:8000';
let charts = {};
let currentMode = 'browse';
let subreddits = [];

const COLORS = {
    bg: '#282828',
    bgSoft: '#32302f',
    fg: '#ebdbb2',
    fgMuted: '#a89984',
    red: '#cc241d',
    green: '#98971a',
    yellow: '#d79921',
    blue: '#458588',
    purple: '#b16286',
    aqua: '#689d6a',
    orange: '#d65d0e',
    gray: '#928374'
};

document.addEventListener('DOMContentLoaded', () => {
    initCharts();
    setupEventListeners();
    loadSubreddits();
    loadData();
});

function setupEventListeners() {
    document.getElementById('refreshBtn').addEventListener('click', loadData);
    document.getElementById('dateRange').addEventListener('change', loadData);
    
    document.getElementById('searchForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const query = document.getElementById('searchInput').value.trim();
        if (query) {
            currentMode = 'search';
            await searchPosts(query);
        }
    });

    document.getElementById('subredditTabs').addEventListener('click', (e) => {
        if (e.target.classList.contains('tab')) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            e.target.classList.add('active');
            currentMode = 'browse';
            document.getElementById('searchInfo').style.display = 'none';
            document.getElementById('postsHeader').textContent = 'Recent Posts';
            loadData();
        }
    });
}

async function loadSubreddits() {
    try {
        const res = await fetch(`${API_BASE_URL}/api/subreddits`);
        subreddits = await res.json();
        
        const tabsContainer = document.getElementById('subredditTabs');
        const searchSelect = document.getElementById('searchSubreddits');
        
        subreddits.slice(0, 10).forEach(sub => {
            const btn = document.createElement('button');
            btn.className = 'tab';
            btn.dataset.sub = sub;
            btn.textContent = `r/${sub}`;
            tabsContainer.appendChild(btn);
        });
        
        subreddits.forEach(sub => {
            const opt = document.createElement('option');
            opt.value = sub;
            opt.textContent = `r/${sub}`;
            searchSelect.appendChild(opt);
        });
    } catch (e) {
        console.error('Error loading subreddits:', e);
    }
}

function initCharts() {
    const chartOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                labels: { color: COLORS.fgMuted, font: { family: 'monospace', size: 11 } }
            }
        },
        scales: {
            x: {
                ticks: { color: COLORS.fgMuted, font: { family: 'monospace', size: 10 } },
                grid: { color: COLORS.bgMuted }
            },
            y: {
                ticks: { color: COLORS.fgMuted, font: { family: 'monospace', size: 10 } },
                grid: { color: COLORS.bgMuted }
            }
        }
    };

    const sentimentCtx = document.getElementById('sentimentChart').getContext('2d');
    charts.sentiment = new Chart(sentimentCtx, {
        type: 'doughnut',
        data: {
            labels: ['Positive', 'Neutral', 'Negative'],
            datasets: [{ data: [0, 0, 0], backgroundColor: [COLORS.green, COLORS.gray, COLORS.red], borderWidth: 0 }]
        },
        options: { ...chartOptions, cutout: '60%', scales: {} }
    });

    const timelineCtx = document.getElementById('timelineChart').getContext('2d');
    charts.timeline = new Chart(timelineCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                { label: 'Positive', data: [], borderColor: COLORS.green, backgroundColor: COLORS.green + '20', tension: 0.3, borderWidth: 2 },
                { label: 'Neutral', data: [], borderColor: COLORS.gray, backgroundColor: COLORS.gray + '20', tension: 0.3, borderWidth: 2 },
                { label: 'Negative', data: [], borderColor: COLORS.red, backgroundColor: COLORS.red + '20', tension: 0.3, borderWidth: 2 }
            ]
        },
        options: chartOptions
    });
}

async function loadData() {
    showLoading(true);
    hideError();

    try {
        const activeTab = document.querySelector('.tab.active');
        const subreddit = activeTab?.dataset.sub === 'all' ? null : activeTab?.dataset.sub || null;
        const days = parseInt(document.getElementById('dateRange').value);

        console.log('Loading data - Active tab:', activeTab?.dataset.sub, 'Subreddit param:', subreddit);

        // Build URL with optional subreddit
        let postsUrl = `${API_BASE_URL}/api/posts?days=${days}&limit=50`;
        let distUrl = `${API_BASE_URL}/api/sentiment/distribution?days=${days}`;
        let timelineUrl = `${API_BASE_URL}/api/sentiment/timeline?days=${days}`;

        if (subreddit) {
            postsUrl += `&subreddit=${subreddit}`;
            distUrl += `&subreddit=${subreddit}`;
            timelineUrl += `&subreddit=${subreddit}`;
        }

        console.log('Fetching:', postsUrl);

        const [postsRes, distRes, timelineRes] = await Promise.all([
            fetch(postsUrl),
            fetch(distUrl),
            fetch(timelineUrl)
        ]);

        const posts = postsRes.ok ? await postsRes.json() : [];
        console.log('Received', posts.length, 'posts from subreddits:', [...new Set(posts.map(p => p.subreddit))]);

        const distribution = distRes.ok ? await distRes.json() : { positive: 0, neutral: 0, negative: 0 };
        const timeline = timelineRes.ok ? await timelineRes.json() : { labels: [], positive: [], neutral: [], negative: [] };

        updateDashboard(posts, distribution, timeline);
        updateLastUpdated();

    } catch (error) {
        console.error('Error loading data:', error);
        showError(error.message);
    } finally {
        showLoading(false);
    }
}

async function searchPosts(query) {
    showLoading(true);
    hideError();
    resetSearchUI();

    try {
        const searchSub = document.getElementById('searchSubreddits').value;
        const sentiment = document.getElementById('searchSentiment').value;

        // Use the streaming analysis endpoint
        const params = new URLSearchParams({ q: query, limit: 30 });
        if (searchSub) params.append('subreddits', searchSub);

        const eventSource = new EventSource(`${API_BASE_URL}/api/search/analysis/stream?${params}`);

        let streamingSummary = '';

        eventSource.addEventListener('status', (e) => {
            const data = JSON.parse(e.data);
            const statusEl = document.getElementById('analysisSummary');
            statusEl.innerHTML = `<span class="streaming-status">${data.message}</span>`;
        });

        eventSource.addEventListener('sentiment', (e) => {
            const data = JSON.parse(e.data);
            document.getElementById('searchInfo').style.display = 'block';
            document.getElementById('searchQuery').textContent = `"${query}"`;
            document.getElementById('searchTotal').textContent = `${data.total} posts`;
            document.getElementById('searchPositive').textContent = `✓ ${data.positive}`;
            document.getElementById('searchNeutral').textContent = `○ ${data.neutral}`;
            document.getElementById('searchNegative').textContent = `✗ ${data.negative}`;

            document.getElementById('postsHeader').textContent = `Analysis: "${query}"`;

            // Update stats
            updateStats(data.total, data.positive, data.neutral, data.negative);

            // Update charts
            charts.sentiment.data.datasets[0].data = [data.positive, data.neutral, data.negative];
            charts.sentiment.update();
            charts.timeline.data.labels = [];
            charts.timeline.data.datasets.forEach(d => d.data = []);
            charts.timeline.update();

            // Update tone badge and bar
            const toneBadge = document.getElementById('analysisTone');
            toneBadge.textContent = data.overall_tone;
            toneBadge.className = 'tone-badge';
            if (data.positive_percent > 40 && data.negative_percent < 30) {
                toneBadge.classList.add('tone-positive');
            } else if (data.negative_percent > 40 && data.positive_percent < 30) {
                toneBadge.classList.add('tone-negative');
            } else {
                toneBadge.classList.add('tone-neutral');
            }

            const total = data.total;
            const posWidth = (data.positive / total * 100).toFixed(1);
            const negWidth = (data.negative / total * 100).toFixed(1);
            const neuWidth = (100 - parseFloat(posWidth) - parseFloat(negWidth)).toFixed(1);

            document.getElementById('sentimentBar').innerHTML = `
                <div class="bar-positive" style="width: ${posWidth}%" title="Positive: ${data.positive}"></div>
                <div class="bar-neutral" style="width: ${neuWidth}%" title="Neutral: ${data.neutral}"></div>
                <div class="bar-negative" style="width: ${negWidth}%" title="Negative: ${data.negative}"></div>
            `;

            document.getElementById('analysisSection').classList.add('active');
        });

        eventSource.addEventListener('summary_chunk', (e) => {
            const data = JSON.parse(e.data);
            streamingSummary = data.accumulated;
            const summaryEl = document.getElementById('analysisSummary');
            summaryEl.innerHTML = streamingSummary + '<span class="streaming-cursor">▋</span>';
        });

        eventSource.addEventListener('complete', (e) => {
            const data = JSON.parse(e.data);
            eventSource.close();

            // Update summary (remove cursor)
            const summaryEl = document.getElementById('analysisSummary');
            summaryEl.textContent = data.summary;

            // Update tone badge
            const toneBadge = document.getElementById('analysisTone');
            toneBadge.textContent = data.sentiment_summary.overall_tone;
            toneBadge.className = 'tone-badge';
            if (data.sentiment_summary.positive_percent > 40 && data.sentiment_summary.negative_percent < 30) {
                toneBadge.classList.add('tone-positive');
            } else if (data.sentiment_summary.negative_percent > 40 && data.sentiment_summary.positive_percent < 30) {
                toneBadge.classList.add('tone-negative');
            } else {
                toneBadge.classList.add('tone-neutral');
            }

            // Update citations
            const citationsGrid = document.getElementById('citationsGrid');
            const allCitations = [
                ...data.positive_examples.map(p => ({...p, sentiment: 'positive'})),
                ...data.negative_examples.map(p => ({...p, sentiment: 'negative'})),
                ...data.neutral_examples.map(p => ({...p, sentiment: 'neutral'}))
            ];

            if (allCitations.length > 0) {
                citationsGrid.innerHTML = allCitations.map(c => `
                    <div class="citation-card sentiment-${c.sentiment}">
                        <a href="${c.url}" target="_blank" class="citation-title">${escapeHtml(c.title)}</a>
                        <div class="citation-meta">
                            <span class="citation-sub">${c.subreddit}</span>
                            <span class="citation-sentiment">${c.sentiment}</span>
                            <span class="citation-score">${c.score} pts</span>
                        </div>
                    </div>
                `).join('');
            } else {
                citationsGrid.innerHTML = '<p class="no-citations">No example posts found.</p>';
            }

            // Show posts table
            updatePostsTable(allCitations);

            showLoading(false);
        });

        eventSource.addEventListener('error', (e) => {
            console.error('SSE error:', e);
            eventSource.close();
            showError('Stream error occurred');
            showLoading(false);
        });

    } catch (error) {
        console.error('Search error:', error);
        showError(error.message);
        showLoading(false);
    }
}

function displayAnalysis(data) {
    const section = document.getElementById('analysisSection');
    const toneBadge = document.getElementById('analysisTone');
    const sentimentBar = document.getElementById('sentimentBar');
    const summary = document.getElementById('analysisSummary');
    const citationsGrid = document.getElementById('citationsGrid');
    
    section.classList.add('active');
    
    // Tone badge
    toneBadge.textContent = data.sentiment_summary.overall_tone;
    toneBadge.className = 'tone-badge';
    if (data.sentiment_summary.positive_percent > 40 && data.sentiment_summary.negative_percent < 30) {
        toneBadge.classList.add('tone-positive');
    } else if (data.sentiment_summary.negative_percent > 40 && data.sentiment_summary.positive_percent < 30) {
        toneBadge.classList.add('tone-negative');
    } else {
        toneBadge.classList.add('tone-neutral');
    }
    
    // Sentiment bar
    const total = data.sentiment_summary.total;
    const posWidth = (data.sentiment_summary.positive / total * 100).toFixed(1);
    const negWidth = (data.sentiment_summary.negative / total * 100).toFixed(1);
    const neuWidth = (100 - parseFloat(posWidth) - parseFloat(negWidth)).toFixed(1);
    
    sentimentBar.innerHTML = `
        <div class="bar-positive" style="width: ${posWidth}%" title="Positive: ${data.sentiment_summary.positive}"></div>
        <div class="bar-neutral" style="width: ${neuWidth}%" title="Neutral: ${data.sentiment_summary.neutral}"></div>
        <div class="bar-negative" style="width: ${negWidth}%" title="Negative: ${data.sentiment_summary.negative}"></div>
    `;
    
    // Summary text
    summary.textContent = data.summary;
    
    // Citations
    let citationsHtml = '';
    
    if (data.positive_examples.length > 0) {
        citationsHtml += `<div><strong>Positive Views:</strong>`;
        data.positive_examples.forEach(c => {
            citationsHtml += `
                <div class="citation-card positive">
                    <div class="citation-title"><a href="${c.url}" target="_blank">${escapeHtml(c.title)}</a></div>
                    <div class="citation-meta">r/${c.subreddit} by ${c.author} · ${c.score} points</div>
                </div>`;
        });
        citationsHtml += `</div>`;
    }
    
    if (data.negative_examples.length > 0) {
        citationsHtml += `<div><strong>Negative Views:</strong>`;
        data.negative_examples.forEach(c => {
            citationsHtml += `
                <div class="citation-card negative">
                    <div class="citation-title"><a href="${c.url}" target="_blank">${escapeHtml(c.title)}</a></div>
                    <div class="citation-meta">r/${c.subreddit} by ${c.author} · ${c.score} points</div>
                </div>`;
        });
        citationsHtml += `</div>`;
    }
    
    if (data.neutral_examples.length > 0) {
        citationsHtml += `<div><strong>Neutral/Informational:</strong>`;
        data.neutral_examples.forEach(c => {
            citationsHtml += `
                <div class="citation-card neutral">
                    <div class="citation-title"><a href="${c.url}" target="_blank">${escapeHtml(c.title)}</a></div>
                    <div class="citation-meta">r/${c.subreddit} by ${c.author} · ${c.score} points</div>
                </div>`;
        });
        citationsHtml += `</div>`;
    }
    
    citationsGrid.innerHTML = citationsHtml;
}

function updateDashboard(posts, distribution, timeline) {
    updateStats(posts.length, distribution.positive, distribution.neutral, distribution.negative);
    
    charts.sentiment.data.datasets[0].data = [distribution.positive, distribution.neutral, distribution.negative];
    charts.sentiment.update();

    if (timeline.labels?.length) {
        charts.timeline.data.labels = timeline.labels;
        charts.timeline.data.datasets[0].data = timeline.positive || [];
        charts.timeline.data.datasets[1].data = timeline.neutral || [];
        charts.timeline.data.datasets[2].data = timeline.negative || [];
        charts.timeline.update();
    }
    
    updatePostsTable(posts);
}

function updateStats(total, positive, neutral, negative) {
    document.getElementById('totalPosts').textContent = total;
    document.getElementById('positiveCount').textContent = positive;
    document.getElementById('neutralCount').textContent = neutral;
    document.getElementById('negativeCount').textContent = negative;
}

function updatePostsTable(posts) {
    const container = document.getElementById('postsContent');
    
    if (!posts?.length) {
        container.innerHTML = '<div class="empty-state">No posts found</div>';
        return;
    }

    const sortedPosts = [...posts].sort((a, b) => (b.score || 0) - (a.score || 0)).slice(0, 25);
    
    let html = '<table><thead><tr><th>Title</th><th>Subreddit</th><th>Score</th><th>Sentiment</th><th>Date</th></tr></thead><tbody>';
    
    sortedPosts.forEach(post => {
        const sentimentClass = getSentimentClass(post.sentiment);
        const date = new Date(post.created_utc).toLocaleDateString();
        
        html += `<tr>
            <td><a href="${post.permalink}" target="_blank">${escapeHtml(post.title)}</a></td>
            <td>r/${post.subreddit}</td>
            <td>${post.score || 0}</td>
            <td><span class="sentiment-badge ${sentimentClass}">${post.sentiment || '-'}</span></td>
            <td>${date}</td>
        </tr>`;
    });
    
    html += '</tbody></table>';
    container.innerHTML = html;
}

function getSentimentClass(sentiment) {
    switch (sentiment?.toLowerCase()) {
        case 'positive': return 'positive';
        case 'negative': return 'negative';
        default: return 'neutral';
    }
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showLoading(show) {
    document.getElementById('loadingMessage').classList.toggle('active', show);
}

function showError(message) {
    const el = document.getElementById('errorMessage');
    document.getElementById('errorText').textContent = message;
    el.classList.add('active');
}

function hideError() {
    document.getElementById('errorMessage').classList.remove('active');
}

function resetSearchUI() {
    const summaryEl = document.getElementById('analysisSummary');
    if (summaryEl) summaryEl.innerHTML = '<span class="streaming-status">Loading...</span>';
    const citationsGrid = document.getElementById('citationsGrid');
    if (citationsGrid) citationsGrid.innerHTML = '';
}

function updateLastUpdated() {
    document.getElementById('lastUpdated').textContent = 'Last updated: ' + new Date().toLocaleTimeString();
}
