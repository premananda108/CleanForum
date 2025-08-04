# Spam Detection System in CleanForum

The system in CleanForum is a hybrid one. It uses two main methods to evaluate each new post:

1.  **Heuristic Analysis**: A set of rules to quickly identify obvious spam.
2.  **Vector Classifier**: Machine learning to find semantically similar spam.

Here's how it works step by step:

### Step 1: Post Creation and Detector Invocation

When a user creates a new post, the API endpoint in `api/posts.py` receives the data and passes it to the `SpamDetector` **before saving**.

### Step 2: Heuristic Analysis

The `SpamDetector` in `services/spam_detector.py` first performs a heuristic analysis. This is a set of simple and fast content checks, such as:

*   **Number of links**: Too many links in a post is suspicious.
*   **Stop words**: Presence of typical spam words ("casino", "free", "earnings").
*   **Message length**: Posts that are too short or too long can be spam.
*   **Uppercase**: A large number of words in CAPS LOCK.

Each rule adds "points" to the `heuristic_score`.

### Step 3: Vector Classifier

In parallel with heuristics, the `SpamDetector` calls the `VectorClassifier` in `services/vector_classifier.py`. This component is the heart of the system:

1.  **Vector Creation**: The post's text is converted into a numerical vector (embedding) using the `SentenceTransformer` model. This vector represents the semantic meaning of the text.
2.  **Search in Redis**: The system performs a vector search in Redis (`FT.SEARCH`). It searches the `posts:vector_idx` index for posts whose vectors are closest to the new post's vector.
3.  **Similarity Score**: If very similar posts are found that were previously marked as spam, the new post's `vector_score` is increased.

### Step 4: Decision Making

The `SpamDetector` combines the `heuristic_score` and `vector_score` into a final `spam_score`. Depending on this score, the post receives one of the following statuses:

*   **Low score (`< 0.3`)**: The post is considered "clean" and is immediately **published**.
*   **Medium score (`0.3 - 0.7`)**: The post is suspicious and is sent for **manual moderation**. It is not visible to regular users.
*   **High score (`> 0.7`)**: The post is almost certainly spam and is immediately **blocked**.

The analysis result, including the reasons and scores, is saved in `post.analysis_details`.

### Step 5: Feedback and Learning

This is a key stage that makes the system smarter.

*   **Moderation**: When a moderator in `moderator_panel.html` approves or rejects a post, their decision is recorded. An approved post becomes a "benchmark for good content," and one marked as spam becomes a "benchmark for spam."
*   **Retraining**: Over time, when enough data from moderators has been accumulated, the retraining process can be started (`/api/moderator/retrain`). This process can further train the vector model on new data, improving its accuracy. The source data for training is in `spam_dataset.json`.

### Key Files to Study:

*   `services/spam_detector.py`: The main orchestrator that combines all checks.
*   `services/vector_classifier.py`: The logic for vector analysis and interaction with Redis.
*   `api/posts.py`: The place where the detector is called when a post is created.
*   `api/moderator.py`: The logic for processing moderator decisions, which is used for feedback.
*   `models/post.py`: The data model where the `is_spam`, `spam_score`, and `status` fields are stored.
