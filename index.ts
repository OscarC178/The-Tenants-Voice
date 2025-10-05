// --- START: CORRECTED FILE for supabase/functions/get-generated-content/index.ts ---
import { serve } from 'https://deno.land/std@0.177.0/http/server.ts'
import { GoogleGenerativeAI } from 'https://esm.sh/@google/generative-ai'

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
}

console.log(`Function "get-generated-content" has been initialized.`);

serve(async (req) => {
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders })
  }

  try {
    const { actionKey, chatHistory } = await req.json()

    const googleApiKey = Deno.env.get('GOOGLE_AI_API_KEY')
    if (!googleApiKey) throw new Error('Missing Google AI API Key')

    const genAI = new GoogleGenerativeAI(googleApiKey)
    const model = genAI.getGenerativeModel({ model: 'gemini-2.5-flash' })

    const conversationText = chatHistory.map(m => `${m.sender}: ${m.text}`).join('\n');
    let actionDescription = '';

    // --- MODIFICATION 1: Simplified switch for clarity ---
    switch (actionKey) {
      case 'email_landlord':
        actionDescription = 'Draft a polite but firm email to the landlord.';
        break;
      case 'dispute_message':
        actionDescription = 'Draft a clear, factual dispute message for a tenancy deposit scheme.';
        break;
      case 'step_by_step_guide':
        actionDescription = 'Create a simple, step-by-step guide on how to proceed.';
        break;
      case 'email_council':
        actionDescription = 'Draft a formal email to the local council\'s housing team.';
        break;
      case 'call_council':
        actionDescription = 'Create a bullet-point list of key points for a phone call to the council.';
        break;
      default:
        throw new Error(`Unknown action key: ${actionKey}`);
    }

    // --- MODIFICATION 2: A more robust and explicit prompt ---
    const prompt = `
      You are an expert AI assistant providing drafting support to UK tenants.
      Based on the following conversation history, your task is to generate a specific document.

      Action Required: ${actionDescription}

      Conversation History:
      ${conversationText}

      Instructions:
      1. Review the entire conversation to understand the user's specific problem.
      2. Generate the requested document with a professional and appropriate tone.
      3. Use placeholders like "[Your Name]" or "[Date]" where needed.
      4. IMPORTANT: Return ONLY the generated text. Do not add any conversational intros or summaries.
    `;

    const result = await model.generateContent(prompt);
    const generatedText = result.response.text();

    // --- MODIFICATION 3: Return JSON with the "text" key that the frontend expects ---
    return new Response(JSON.stringify({ text: generatedText }), { 
      headers: { ...corsHeaders, 'Content-Type': 'application/json' } 
    })

  } catch (error) {
    console.error("Error in get-generated-content:", error.message);
    return new Response(JSON.stringify({ error: error.message }), { 
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }, 
      status: 500 
    })
  }
})
// --- END: CORRECTED FILE ---