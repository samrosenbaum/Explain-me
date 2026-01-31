import Anthropic from "@anthropic-ai/sdk";

const anthropic = new Anthropic();

const SYSTEM_PROMPT = `You are a helpful assistant that explains technical jargon, acronyms, and complex concepts in simple, easy-to-understand terms.

Your job is to:
1. Identify any technical terms, acronyms, or jargon in the text
2. Explain what they mean in plain English
3. Provide context for how they're typically used

Guidelines:
- Be concise but thorough
- Use analogies when helpful
- If there are multiple technical terms, explain each one
- If the text is already simple and has no jargon, say so briefly
- Format your response for Slack (use *bold* for terms, bullet points for lists)
- Keep explanations friendly and approachable
- If you're unsure about a company-specific acronym, note that it might be internal jargon`;

export async function explainJargon(text: string): Promise<string> {
  try {
    const message = await anthropic.messages.create({
      model: "claude-sonnet-4-20250514",
      max_tokens: 1024,
      messages: [
        {
          role: "user",
          content: `Please explain any technical jargon or complex terms in this text:\n\n"${text}"`,
        },
      ],
      system: SYSTEM_PROMPT,
    });

    const content = message.content[0];
    if (content.type === "text") {
      return content.text;
    }

    return "I couldn't generate an explanation. Please try again.";
  } catch (error) {
    console.error("Error calling Claude API:", error);
    throw new Error("Failed to get explanation from AI service");
  }
}
