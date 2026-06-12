// VVSdeal betalings-API (Cloudflare Worker)
//
// To endpoints:
//   POST /create-checkout-session  - opretter en Stripe Checkout-session for kurven
//   POST /webhook                  - Stripe webhook, gemmer gennemførte ordrer i KV
//
// Priser valideres ALTID server-side mod den offentlige products.js,
// så en kunde ikke kan manipulere prisen i browseren.

import Stripe from "stripe";

const TILLADTE_OPRINDELSER = new Set([
  "https://www.vvsdeal.dk",
  "https://vvsdeal.dk",
  "http://localhost:8742",
]);

function corsHeaders(request) {
  const origin = request.headers.get("Origin") || "";
  return {
    "Access-Control-Allow-Origin": TILLADTE_OPRINDELSER.has(origin) ? origin : "https://www.vvsdeal.dk",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
  };
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const cors = corsHeaders(request);

    if (request.method === "OPTIONS") {
      return new Response(null, { headers: cors });
    }

    const stripe = new Stripe(env.STRIPE_SECRET_KEY, {
      httpClient: Stripe.createFetchHttpClient(),
    });

    try {
      if (url.pathname === "/create-checkout-session" && request.method === "POST") {
        return await opretCheckoutSession(request, stripe, cors);
      }
      if (url.pathname === "/webhook" && request.method === "POST") {
        return await haandterWebhook(request, env, stripe);
      }
    } catch (err) {
      return new Response(JSON.stringify({ error: err.message }), {
        status: 500,
        headers: { ...cors, "Content-Type": "application/json" },
      });
    }

    return new Response("Not found", { status: 404, headers: cors });
  },
};

async function hentProdukter() {
  const res = await fetch("https://www.vvsdeal.dk/products.js");
  const tekst = await res.text();
  const i = tekst.indexOf("const SHOP_DATA = ") + "const SHOP_DATA = ".length;
  const data = JSON.parse(tekst.slice(i, tekst.lastIndexOf(";")));
  const opslag = new Map(data.produkter.map(p => [p.id, p]));
  return opslag;
}

async function opretCheckoutSession(request, stripe, cors) {
  const body = await request.json();
  const produkter = await hentProdukter();

  const line_items = [];
  for (const linje of body.linjer || []) {
    const p = produkter.get(linje.varenr);
    const antal = Math.max(1, Math.min(99, parseInt(linje.antal, 10) || 0));
    if (!p || antal < 1) continue;
    line_items.push({
      price_data: {
        currency: "dkk",
        product_data: { name: p.navn },
        unit_amount: Math.round(p.pris * 100),
      },
      quantity: antal,
    });
  }

  if (line_items.length === 0) {
    return new Response(JSON.stringify({ error: "Tom kurv" }), {
      status: 400,
      headers: { ...cors, "Content-Type": "application/json" },
    });
  }

  const fragt = Math.max(0, Math.round((body.fragtDKK || 0) * 100)) / 100;
  if (fragt > 0) {
    line_items.push({
      price_data: {
        currency: "dkk",
        product_data: { name: `Fragt: ${body.levering || ""}` },
        unit_amount: Math.round(fragt * 100),
      },
      quantity: 1,
    });
  }

  const kunde = body.kunde || {};
  const session = await stripe.checkout.sessions.create({
    mode: "payment",
    line_items,
    customer_email: kunde.email || undefined,
    success_url: "https://www.vvsdeal.dk/tak.html?session_id={CHECKOUT_SESSION_ID}",
    cancel_url: "https://www.vvsdeal.dk/?betaling=annulleret",
    metadata: {
      kunde_navn: kunde.navn || "",
      kunde_telefon: kunde.telefon || "",
      kunde_adresse: kunde.adresse || "",
      kommentar: kunde.kommentar || "",
      levering: body.levering || "",
      linjer: JSON.stringify((body.linjer || []).map(l => ({ varenr: l.varenr, antal: l.antal }))),
    },
  });

  return new Response(JSON.stringify({ url: session.url }), {
    headers: { ...cors, "Content-Type": "application/json" },
  });
}

async function haandterWebhook(request, env, stripe) {
  const signatur = request.headers.get("stripe-signature");
  const raaKrop = await request.text();

  let event;
  try {
    event = await stripe.webhooks.constructEventAsync(
      raaKrop,
      signatur,
      env.STRIPE_WEBHOOK_SECRET,
      undefined,
      Stripe.createSubtleCryptoProvider()
    );
  } catch (err) {
    return new Response(`Webhook-fejl: ${err.message}`, { status: 400 });
  }

  if (event.type === "checkout.session.completed") {
    const session = event.data.object;
    const ordre = {
      id: session.id,
      ordrenummer: "VD-" + session.id.slice(-10).toUpperCase(),
      email: session.customer_details?.email || "",
      totalDKK: (session.amount_total || 0) / 100,
      metadata: session.metadata || {},
      tidspunkt: new Date().toISOString(),
      status: "betalt",
    };
    await env.ORDERS.put(session.id, JSON.stringify(ordre));
  }

  return new Response("ok");
}
