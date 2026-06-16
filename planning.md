## Intention of this project

Create a bot for the messaging platform Discord that rates interactions between users on a server. The bot is **always** active on the server, and performs its job on a regular basis.

## Functions of the bot

**Function 1**: When a 'bad' interaction occurs, the bot displays a message in the chat indicating that such an event has happened. The interaction is then stored and ranked amongst other interactions, maintaining a leaderboard of the 'worst' interactions. Therefore, the message displayed is:

"Bottom [insert place here] interaction of all time."

**Function 2**: When a user uses the '/rate' command in chat, the bot will find the nearest above interaction between users, score it, and return a message indicating the score of the interaction out of 10. The message displayed is:

"This interaction was a [x]/10"

## Interaction Scoring

The score of the interaction should be scored as follows:

**1.** Intellectual Content - interactions where intellectual topics are discussed should be scored very favorably, whereas one's without any intellectual content should not be. 

**2.** Use of slurs - interactions that utilize slurs should be scored negatively. The use of the n-word, or any word trying to imitate it, specifically should be scored very negatively.

**3.** Any interaction that grok deems is "retarded" should be scored very negatively, and should always trigger function 1.

## Architecture

For scoring interactions, use the grok api through OpenRouter. Specifically, use the grok 4.3 model that is described in detail in grok_model_spec.md

//Fill in other architecture notes here

