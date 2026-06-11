Scenario: Fetch transcript for a valid video
    Given a video ID with an available transcript
    When youtube-transcript-api fetches the transcript
    Then the raw transcript is saved to .cache/transcripts/{video_id}.json
    And the transcript contains text, start time, and duration per segment

  Scenario: Clean garbled DRBD terminology
    Given a raw transcript containing "D R B D" or "derby"
    When the cleaner processes the transcript
    Then "D R B D" is replaced with "DRBD"
    And "derby" in technical context is replaced with "DRBD"
    And "lin store" is replaced with "LINSTOR"
    And "lin bit" is replaced with "LINBIT"

  Scenario: Chunk cleaned transcript into passages
    Given a cleaned transcript of arbitrary length
    When the chunker processes it
    Then it is split into passages of approximately 500 words
    And each chunk retains metadata:
      | field       | value                    |
      | video_id    | YouTube video ID         |
      | video_title | title of the video       |
      | timestamp   | start time of the chunk  |
      | source      | youtube:linbit           |

  Scenario: Save chunk as text file for ingestion
    Given a cleaned chunked transcript
    When the fetcher saves the output
    Then each chunk is saved as a .txt file under data/docs/transcripts/
    And the filename is {video_id}_chunk_{n}.txt
    And ingest_once.py can process it without modification

  Scenario: Skip already fetched videos
    Given a video ID that exists in .cache/transcripts/
    When the fetcher runs again
    Then the video is skipped
    And no duplicate chunks are created in ChromaDB

  Scenario: Channel crawl is interrupted
    Given yt-dlp is fetching video IDs
    When the process is interrupted or network fails
    Then already fetched video IDs are preserved in cache
    And the next run resumes from where it left off

  Scenario: Full pipeline run
    Given the LINBIT YouTube channel URL
    When ratgeber_transcript_fetcher.py is executed
    Then all videos are fetched, cleaned, chunked and saved
    And a summary is printed showing:
      | videos found     |
      | transcripts fetched |
      | videos skipped   |
      | chunks saved     |

  Scenario: Video is in German
    Given a Linbit video with a German transcript
    When youtube-transcript-api fetches the transcript
    Then the German transcript is accepted
    And detect_language identifies it as German
    And it is chunked using de_core_news_sm spaCy model
    And it is saved and ingested like any English transcript

  Scenario: Video has both English and German transcripts
    Given a video with multiple transcript languages available
    When youtube-transcript-api fetches the transcript
    Then English is preferred
    And German is used as fallback
    And unsupported languages are skipped

  Scenario: Video is a short clip under 60 seconds
    Given a video shorter than 60 seconds
    When the fetcher processes it
    Then it is skipped as too short to contain useful knowledge
    And it is logged as skipped with reason "too short"

  Scenario: Transcript is auto-generated with no punctuation
    Given a raw auto-generated transcript with no sentence boundaries
    When the cleaner processes it
    Then spaCy is used to infer sentence boundaries
    And the cleaned text reads as proper prose

  Scenario: Transcript contains sponsor or intro segments
    Given a transcript with "today's video is sponsored by"
    When the cleaner processes it
    Then the segment is stripped
    And only technical content is chunked

  Scenario: ChromaDB already contains chunks from this video
    Given a video whose chunks are already in ChromaDB
    When the fetcher runs again
    Then existing chunks are not duplicated
    And the video is skipped with reason "already ingested"

  Scenario: data/docs/transcripts/ directory does not exist
    Given the transcripts directory is missing
    When the fetcher attempts to save chunks
    Then the directory is created automatically
    And saving proceeds without error

  Scenario: Generate ingestion report
    Given a completed fetcher run
    When the summary is printed
    Then it includes:
      | total videos on channel        |
      | videos with transcripts        |
      | videos skipped - no transcript |
      | videos skipped - too short     |
      | videos skipped - already done  |
      | videos skipped - non-English/German |
      | total chunks saved             |
      | total chunks ingested to ChromaDB |

  