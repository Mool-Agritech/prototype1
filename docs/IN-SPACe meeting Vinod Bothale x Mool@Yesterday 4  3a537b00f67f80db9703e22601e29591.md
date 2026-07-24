# IN-SPACe meeting Vinod Bothale x Mool@Yesterday 4:00 PM

Summary

### Action Items

- [x]  Review InSpace TAF (Technology Adoption Fund) application process and brochure on InSpace website
- [x]  Create WhatsApp group with Vinod for ongoing communication and resource sharing
- [x]  Share GitHub repository with satellite data specifications to Vinod
- [ ]  Explore Tamil Nadu state funding schemes and connect with deputy director contact
- [ ]  Connect with IMD for weather data access through Vinod's network
- [ ]  Connect with Maharashtra Remote Sensing Centre agriculture specialist (PMFBY expert, retiring this year) for granular yield data guidance
- [ ]  Build SAR data processing pipelines as backup to optical satellite data
- [ ]  Register formal requests on InSpace portal to document expert interactions

### 🎯 Mool's Competitive Differentiation

The advisor asked detailed questions about how Mool differs from competitors. Key differentiators presented: 

- **==Practice-linked pricing==**: Premium rates improve as farmers adopt better agroecology practices — competitors like Shema, Pula, Ibiza, and InRisk don't link pricing to actual farming practices
- **==Plot-level triggers==**: Targeting individual plot-level vs PMFBY's block-level settlement, directly attacking basis risk gap
- **==Tenant farmer inclusion==**: Building risk history for landless/tenant farmers using land-based practice data from 2001 onwards — traditional methods only serve land-owning farmers
- **==Orchestrator model==**: Not holding insurance risk itself, just coordinating between insurers, farmers, and other partners — advisor explicitly liked this approach for speed and reduced regulation
- **==SHG distribution==**: Using self-help groups as B2B2C channel, framing as family well-being program

**Why competitors aren't doing this**: InRisk and Satshaw sell to insurers/banks (different customer); Shema owns insurance layer but doesn't link to practice; practice-linking is operationally hard, expensive, and slow with thin margins and trust barriers 

### 📡 Technical & Data Strategy Discussion

**Current data stack**: 

- Google Earth Engine (Sentinel, Chirps) — primary reliance
- ISRO Bhuvan — whitelisted but server is unstable, data doesn't go back far enough
- Building backtest and nowcast models; forecast comes later
- IMD data not yet incorporated

**==Critical technical concerns raised by advisor==**: 

- **Weather data granularity**: IMD and other weather data sources are coarse (1-2 degree grid) and need to be spatially matched to high-resolution satellite data
- **==Operational sustainability==**: For pilot, test data is fine, but must ensure continuous, sustained data access for any region at scale (Karnataka, Tamil Nadu, Kerala, Andhra Pradesh)
- **==Backup strategies essential==**: If one satellite fails or optical data unavailable due to monsoon clouds, what's the plan?
- **SAR data pipeline**: SAR works through clouds but processing methodology is completely different from optical — team confirmed building those pipelines

**Specific data access issues**: 

- EOS 8-day cloud-free composite data inaccessible on ISRO API
- Bhuvan server down for 2-3 days
- Advisor offered to help investigate underlying data sources and connect to IMD

### 💰 Funding Pathways — InSpace & Beyond

**==InSpace Technology Adoption Fund (TAF)==**: 

- **Eligibility**: TAF looks for **innovation, uniqueness, and market potential** — doesn't require company registration
- Can apply for **pilot-stage funding**
- Focus application on: uniqueness, why competitors aren't doing it, background rationale
- Application details available in InSpace website brochure
- Advisor can help refine proposal and connect to right people for clarity

**InSpace Seed Funding Scheme**: 

- Up to ₹1 crore funding with equivalent company co-funding requirement
- Some agriculture and marine startups already selected

**State-level schemes**: 

- **Tamil Nadu**: ₹50 lakh grants for startups (advisor was jury) — constraint is company must be registered in state or have linkage
- Advisor suggested exploring Maharashtra, Andhra Pradesh, Karnataka state schemes with similar models

**Readiness assessment**: Advisor confirmed TRL 3-4 level is sufficient for TAF — reviewers assess **team composition, innovation, problem clarity, feasibility** 

### 🌾 Implementation & Distribution Model Validation

**Advisor's positive feedback on SHG approach**: 

- Appreciated team's ==B2B2C model through self-help groups== rather than direct farmer platform access
- Confirmed SHGs are very active in South India: **==Kerala and Karnataka are top two, Andhra Pradesh has full stack built out, Tamil Nadu and Telangana also strong==**
- Team already using SHG presence as site selection metric (Maharashtra, Kerala, Karnataka prioritized over sparse Haryana/Delhi)

**Learning from Andhra Pradesh APCNF model**: 

- 1.8 million farmers moved completely off synthetic inputs over past 10 years
- Built 10-year on-ground infrastructure with women SHGs, youth, farmer experts
- Farmers create own fertilizers, use own seeds, have peer lending through local offices

**Government context**: 

- Advisor (former Maharashtra Remote Sensing Centre director) shared that 15 years ago, a minister highlighted the compensation fraud problem — farmers claiming payouts without actually sowing crops
- Government was spending ₹1,200-1,300 crore in Maharashtra alone on crop failure compensation
- Satellite verification of "was the field actually cropped" was seen as critical even then

### 🔍 Open Technical Questions & Data Challenges

**Granular yield data**: 

- Team needs **revenue circle or insurance unit level historical yield data** (going back to 2001) for weighted composite index in insurance model
- Currently only have district-level data for Maharashtra (tonnage/kg for cotton, soybean, etc.)
- ==Without granular data, will have to use uniform weight for entire district rather than crop and revenue-circle specific weightage==

**Advisor's guidance**: 

- Farm-level yield data doesn't exist systematically — it's manual reporting by local survey officers
- FASAL system uses statistical estimation: stratify India by historical yield, sample representative data, extrapolate
- PMFBY recently agreed on a solution combining manual reports and remote sensing estimates
- Suggested connecting with Maharashtra agriculture scientist who worked on PMFBY (retiring this year, could be advisor)

### 📊 Project Stage Assessment

**Current stage**: 

- Working toward GCL competition deadline as springboard
- Backtest stage mostly complete, nowcast in progress
- Model on GitHub, still tweaking specifics
- **Not yet incorporated** — will incorporate after successful pilot

**Team composition presented**: 

- Sneha: Imperial MSc cleantech innovation, design/UX background, Mumbai-based
- Akshat: NYU CS, startup building experience
- Yug: Remote sensing and ML, satellite data experience
- Aria: Financial engineering and risk analysis, actuarial modeling
- Srishti: CS/software, full stack, finance experience, soil sampling projects
- Carlos: 7 years environmental compliance, environmental law, going to Imperial for environmental tech

### 🗒️ Items for Decisions & Meeting Log (Mool — GCL Team Hub)

1. **==InSpace TAF identified as primary Phase 1 funding target==** — TRL 3-4 sufficient, no incorporation required, advisor support available 
2. **Data sustainability strategy confirmed as critical**: Must document backup plan for satellite failures and monsoon cloud cover before scaling 
3. **SAR pipeline development elevated to priority**: Essential backup for optical data during monsoon 
4. **Tamil Nadu state scheme connection offered**: Deputy director contact + ₹50L grant precedent 
5. **IMD data access pathway opened**: Advisor can facilitate connection 
6. **PMFBY agriculture specialist connection**: Can advise on granular yield data workarounds and may be advisor candidate 
7. **Kerala and Karnataka confirmed as high-potential SHG regions** alongside Maharashtra and Andhra Pradesh 
8. **State registration strategy consideration**: May need Maharashtra/Karnataka/Tamil Nadu incorporation angle for state schemes 

### ❓ Points Requiring Clarification

- **Granular yield data workaround**: How to build weighted composite index without revenue-circle level historical yield? Is NRSC 1:50,000 or 1:10,000 land use map masking approach sufficient?
- **EOS 8-day cloud-free data**: What are the underlying data sources ISRO uses to generate this composite, and can we access those directly?
- **Hyderabad disaster-focused company**: Advisor mentioned a company in similar space but couldn't recall name — to follow up via WhatsApp
- **Village Resource Center scheme**: Advisor mentioned discontinued scheme — unclear if any states revived it

Notes

look into advisory services for disaster relief companies

In the summary focus on the points made by the advisor

Transcript

Bye.

You got Like it's coming from both places so it's Echoing.

Hi, Zed. Is this?

No, I think that was from Jung Zen.

Yeah, let me check.

because there's two devices. Yup, now it's fine.

yeah i think now it's fine now it's not echoing So, hello, sir.

We are team Mool. She is through speed. She is Sneha. She is currently doing her Masters. in Imperial College London And this is Akshay. He is currently studying in New York University. and we are building this Mool company. uh, on the satellite data for the respective farms and Based on its analysis, we help insurance companies to give parametric payouts. and advise climate resilient farming to farmers also.

Right, right. The base is for... Sorry, you finished your talk?

Yeah.

So Sneha will explain you the business model. Mm-hmm.

Absolutely. Hello, sir. Thank you so much for taking the time. So, yes, as Yog said, we're basically trying to build a model that will make climate resilient practices a viable choice for smallholder farming in India. And the main challenge that we are tackling is that India's poorest farmers actually have no land title, no credit, and they're borrowing at very high informal rates, 50% and this means that even one bad season like any climate shock puts them into this unending cycle.

And we are currently targeting Vidharba in Maharashtra as our pilot because it's kind of at the... Worst end of this, they have the highest farmer suicides and in 2023-24, they roughly had about 60% drought hit farmers that got no insurance payout from any of the traditional methods.

Hmm.

So what we are trying to do is move farmers into low input climate resilient agriculture And we want to use satellite based parametric insurance to cushion that change, like basically reduce the risk for them so that All of these practices aren't such a gamble or like an experiment for them. So we will not, as a company, we won't be holding the risk ourselves. Nor will we be selling directly to the farmer, but we'll be the orchestrator.

Hmm.

Mm-hmm.

We'll help design the insurance product.

We'll verify the practices on the ground throughout the entire process with the help of on-ground local self-help groups.

And we'll help all of the partners come together into this one program, which is built around family well-being, not just agriculture, but all around well-being for these families. That's our big picture. We're trying to sell resilience and actually not just look at reducing harm, but look at long-term solutions.

Yeah.

And there's a model that we're sort of like learning from.

Yeah.

So in Andhra Pradesh over the past 20 years, I'm not sure if you're aware, but there is a program called APCNF.

They are basically doing, it's called Andhra Pradesh something for natural farming.

So they spent 10 years sort of developing the on ground infrastructure with women self help groups, youth hiring, farmer experts. And over the past 10 years from 2016 to today, they have successfully managed to get 1.8 million farmers completely off of synthetic inputs, which means the farmers don't go and buy seeds externally. They don't use fossil fuel based fertilizers, pesticides. They don't get into debt, all of that cycle. So they use practices that are like, they take the cow dung and cow urine and the inputs from their own farm.

They create fertilizers for themselves. They use the seeds that their own plants produce for the next season. And then all of this has a bunch of layers.

everything falls apart. for a specific, let's say, 10 farm, 20 farm collection will have like a office, right? And they'll have their own funds, their own equipment, and they lend to the peers. So it's much more like sort of resilient among people themselves instead of like a top-down infrastructure where there's like, okay, the center is like, okay, we're going to give 10,000 crores in subsidies and then you can only farm with cotton.

And then suddenly there's a drought. So we're using this model to learn from. As of today, we have created a model which is up on GitHub. We're still tweaking out the specifics, but we wanted to get your view on the entire business model and what you think of the implementation idea. Any advice and any feedback is helpful.

Yeah, thank you Sneha and Akshat for giving this short brief. And before that, I would like to know more about all of you. I am really fascinated that you came to this particular problem domain. but we also would like to know how actually you entered up to this point. I mean, what give you an idea that to enter in this domain as well what is your background I mean what does because that also makes a lot of difference sure so on so I think I'll be interesting to then we can continue discussion also I have some I mean some idea I mean who are all doing what kind of thing in this particular sector but would also discuss that part and the kind of technology inputs which are going into this so that you can build a kind of a robust product or I mean, the product which people can trust.

Yes. Maybe Sneha what is your background? Yeah, sure.

Yes, absolutely.

I'll also give you a brief of the entire team as well.

Yes.

So I am actually going to go to Imperial to do my master's in clean tech innovation. So it's like a combination of climate science as well as entrepreneurship.

That's what the program revolves around. I have spent the last year.

So I'm based in Mumbai.

I've spent the last year diving into different types of climate projects from waste in Mumbai to the waterways and most recently agriculture. I think it All comes from China.

I'm trying to get into impact in a big way, specifically for India and the Global South.

That has been my focus with these projects. But I also have a background in design and UI UX, so user experience design. That's people and actually working with people and developing solutions for them. That's what I specialize in. But our team is actually very varied. We have people from India, Colombia, as well as China. And everybody is very Global South focused. We have financial engineering and risk analysis background.

So, you know, experience in actually pricing such products. as well as Yug has remote sensing and machine learning background, and he has actually worked with satellite data. So that has been very helpful in building these products. So Akshat has actually finished his degree at NYU and he has a lot of experience in building startups and he has a computer science background. So they go really well together for, you know, building this venture.

And we also have Srishti who has a computer science and software engineering background as well as full stack experience.

And she has done some projects in soil sampling.

So that's also been very helpful. And Carlos, who's from Colombia, he has about seven years of experience in environmental compliance. So he has done environmental law and he will now be going to Imperial to do environmental technology. Yeah. But for the past seven years, he's been working in compliance.

Yeah.

So yeah, it's the skill sets have have come like the It's come together really well.

So, I'm going to write based in. Good.

Yeah, something you're telling. No, no, please go ahead.

No, this already you have registered Mool.

He's on a call.

No, we have not. This is a very nascent idea. It was primarily focusing on Yeah.

Yes, how long will it take? No, no, no, it's in the house.

Yeah, sorry. There was a call.

No, I saw.

Akshat Yavasthani.

Yeah.

Yeah, I was saying primarily right now we are looking at this competition called the DCL, which is why we are sort of working on a timeline right now. And we're going to use this as a springboard to just like develop the first version of the model, the software. We've been reaching out to folks across financial compliance, remote sensing, a bunch of these people, which is how we got in touch with you.

So we haven't incorporated formally, but I think if the pilot seems worthy of it, We'll probably do it soon enough. Yeah.

Yeah, so.

So yeah, I'll check you out. Akshay, you have a computer science background. Who are you saying the finance part?

We have two people. Srishti has some experience in the finance part and then Arya who is the Chinese girl, she has some experience in the finance part. So she is doing the actuarial modeling.

They are not in the meeting.

They are not in the meeting. They both had prior commitments.

And what I was asking is whether you have already registered a Mool or you have to register?

No, that's what I was saying. We have not incorporated Mool yet. But if the pilot is sort of successful, then that is the plan. Yeah. But yeah, so I mean, that's how we came to this idea. We were like, how can we get out of small circularity, you know, like small bandaid like solutions, and actually have a long term solution that helps a big community serve themselves and the climate and is also sort of a profit making vehicle.

So I think this structure that we've come down to at least does most of that. And now we are trying to get the app granular data in terms of the model. So we've started with Google Earth engines data. So we've got a bunch of that satellite data. We started using ISRO's Bhuneti data also. So we have some data from there. We got whitelisted for a few IPs. But the server is quite shaky. It comes on and off. It's not too reliable.

Some data is not going long back enough. So we've been mostly relying on the Google Earth Engine. to create our backtest as well as create our nowcast. So we're creating two main models on the climate side. That's the good news. sorry now cause data how are you getting Nowcast data also we're using mostly Google Earth Engine. So Sentinel, Chirps, all of this stuff. And we're using some of ISRO's data as well. The specifics I can send you the GitHub and then you can see all the data points that we have. But yeah. IMD also I guess?

IMD also a little bit data we have. But I don't... Have we incorporated that, Yoh? Not yet, right? The IMD data?

No, no, no.

Not IMD. Not yet, no. Not IMD. Thank you.

So yeah, one technical aspect in this is because you are going to at a farm level like granular level, although you can get all other data sets like satellite or even other data sets you know quite a defined and at high resolution i mean prices could be anything but at least you can get the data and second part is weather related which is typically they are the graded products right i mean one degree two degrees graded products from various places like imd and uh imd also have very coarse i mean it's not a very highly dense sorry observation data but ultimately that climate data you have to bring to the level of a spatial data input what you are getting from satellite any other satellite So that then you can actually make use them in conjunction and then coming out with your technical results.

Second part which I was also talking to you yesterday, because you were talking about the business model. You must know who are all your competitors at present. Absolutely. Who are all jumping into this particular sector because this is Very good sector definitely. and it has a lot of bigger people are affected, population number of people who are working into this and getting affected is quite large.

Yes. So, Vizarbha could be a starting point to just take off. But definitely it has got a market potential everywhere. Yes. Typically, if you see even in Maharashtra kind of thing, the amount of compensation government has to give in all these cases is too high.

Okay.

Mm-hmm.

Yes. Earlier I was also director of Maharashtra Remote Sensing Centre, I am long back, 15 years back almost. And one of the minister was talking to me, okay. That time, I mean it is very rare that ministers talk technical things and discuss technically the point but he was discussing with me and he was asking me, and why you people are not thinking of some platform like this or have done anything on this compensation part.

Because we were doing at that time, that time it was, I mean, we were doing with the course resolution satellite data and giving the inputs to the government that, okay, which are the areas which are affected by let us say hurricane, which are the affected by the floods or so that people like someone ask for compensation, you know, whether they were really affected or not. How much transition has to be given is another part.

But first of all, and there are a lot of fake requests coming from Although he has not sown the crop, but he will demand the compensation that his crop is spoiled. So, he was just mentioning that okay at least even if you know at the beginning that you How much cropping has been done in this particular area? At least field is cropped. If it is cropped, I am ready to pay full compensation. But if it is not cropped and asking for the compensation, then it is really a bad situation where government is really getting penalized for it.

What has not happened, you are paying for that. So huge amount of money, even that time it was something like 1200 crore, 1300 crore for a Maharashtra level state to be given by the government as a compensation for the various events of crop failures. Maybe the weather or sudden natural calamities or something like that. So, it is a, I mean, the point of, I mean, mentioning this is that, okay, yes, it is very of relevance and importance.

typically all engineers don't get into this level of agriculture or farm level of this that's why i was wondering how people have come to this Yeah. Second part which I was thinking and I possibly liked that what Sneha was mentioning. Typically, one question comes that how formal can access your platform because they are not as worthy of technological advancements and whatever we do i mean we may build a very good product but still how they get a connected so you trying to restrict to not actually go into the detail of that but self-help group at the top level so that model i also feel it's a better model Yes.

And I mean, if you consider self-help group as one of the business is to kind of be to be venture rather than a B2 Correct. Yes. So I think that kind of thing should work better than this. And some places, wherever the self-help groups are quite active, This may work well. Even South India, Tamil Nadu, Guadeloupe, they are quite active.

Kerala and Karnataka were the top two ones that came up. So, we've also been using that as a metric of which places to tackle first. Andhra Pradesh was amazing. They had this full stack built out. But for instance, Haryana and Delhi is very sparse. There's no self-help group assimilation. So, Karnataka, Kerala and Maharashtra were the top ones that we came up with.

that is the one i think which i mean that you can look for that anyway you already because since you have done this homework i am sure you would have already looked into this uh situation yeah then coming was that who are the competitors like You know, last 3-4 years suddenly many companies came into the agriculture market.

Yes.

Yes.

Yes. Tech market, agri-tech market.

and there would be at least some 30 companies, agri-tech companies who are working on various scenarios.

One of the bigger companies is Cheshire.

I mean, the name is very well known to the people, I am sure, and subsidy model and all So what is their offering?

Yeah.

How do you compete with them?

Yesterday I was talking to you about parametric approach, what you are taking is not dismissing with them.

I would love to elaborate on that. You did share some questions with us and we were specifically working on that. So, yeah, going into the competitors, one of the main points that we saw was competitors are not linking their pricing to the actual practices.

I mean, I would like to hear about that more.

Bye. Thank you.

So the fact that we are focusing on the agroecology and the climate resilience, we are also pricing that into the actual premium and payout. So as farmers use better practices, they're going to get better premium rates.

That's one thing that we haven't seen across competitors like Shema, Pula, Ibiza, InRisk.

Yeah.

Hmm.

These are some competitors that we were looking at. And in terms of the actual trigger, We are also looking at plot level trigger.

Mm-hmm.

Mm-hmm.

PMFBY currently settles at block level.

So we're going even granular, which attacks that basis risk gap that is there. And we are serving tenants and landless smallholder farmers as well. So that's a big one because currently the traditional methods, including Satshah or PMFBY, they are looking at farmers that own the land. because they don't have a way to track tenant farmers. So we are creating those systems as well.

And then again, looking at the way Shema and Satshaw are working, we are not actually holding the risk. We are just orchestrators. So, Because... Yeah Look.

I like that particular part.

It allows us to move faster. It doesn't have that much regulation problem.

So as an orchestrator, this is a good model. I feel it's a good model rather than taking a risk there.

Can I add one more thing, Sneha? In terms of the tenant farmers, how we're doing that is that we're building a risk history for them.

Thank you. Yes.

Usually what you do when you're going for insurance or a loan is you have a credit score from your actions on your loans, whatever. But since these people are usually not registered with the government formally, or they might not have that much formal documentation, we are using their land as the basis. So their farming practices over time. So we have data from like 2001. Their farming practices over time dictate how well they get the insurance premium.

So this is the first time that this is happening within at least among the competitors we know this is one point which is completely unique as well as the other things that Sneha has said. Yeah.

Yep, absolutely.

And the last leverage that we have is the distribution via the SHGs and framing it as a family program that we already touched upon.

Hmm.

So just to elaborate on why are the competitors not doing this?

Because if we were able to come up with it, why are they not doing it?

So there's, again, different reasons from our study. InRisk and Satshaw are currently selling to insurers or banks. They are not looking at smallholder distribution at all because their customer is different. And Shema owns the insurance layer. They are a licensed insurer, but they are not linking to practice. And then practice linking is operationally hard. So that actual on-ground verification, like linking satellite data to geofence photos and QR on the ground and mobilizing the community, it is quite extensive, expensive, as well as slow.

um you Hmm.

So these data firms usually tend to avoid that.

which is something we are getting into.

Mm-hmm.

And then also, at least in the beginning, we are looking at thin margins. We're looking at language barriers, trust barriers. So we are coming up with ways to deal with that.

But these are the barriers why the other incumbents are not really going into this route.

And finally, the tenant farmers are unattractive because there is no documentation. So it's not the KYC process is not very easy.

Yeah, but other part what I want you to focus is.

So that's why these are the barriers that we are planning to cut through. Yeah.

like for testing purpose or for building a pilot you may get a data or satellite data weather data all those things and you will be able to showcase let us say okay But you have to also figure out how do you do the same thing on operational basis for any area. any given area for example let us say You do it for a pilot in a weather bar. But ultimately you have to scale to Karnataka, Andhra Pradesh, Tamil Nadu or Kerala kind of thing.

and for any and request could come from anywhere right correct so So then whatever your particular model is dependent on the inputs, Those inputs, how do you ensure that you will get in the continuous mode? Continuous mode, at sustained mode, that where you want, when you want. Yes. That part you have to make sure because let us say if you think of Sentinel data or GoogleOh, attention. Yeah. So... that you can figure out that okay this particular dot input which is going to my model is sustainably available for the at least region where you are going to make a business If any request comes specifically in the season that you are interested in, How do you tackle and in case In case of not availability, what is your backup plan?

Okay.

So also, there is a couple of data sets that are not showing available on the ISRO Moonendy API platform. I was wondering if that is something that you have any reach into or you can help us with in terms of getting that data access?

Which data you are talking about? Which sensor? This forum?

We needed EOS eight-day cloud-free composite data because a large part of the sensing is to do with rainfall and during monsoons, we need cloud-free data. Now that seems to be switched off or inaccessible on the API that we can access. And also, Ute has been having problems with the server being down for the past two, three days. So I was wondering if there's a more direct channel where we can get stable access because that's a big part of what the model depends on.

No, one thing what we can think of because if they're taking this eight day cloud free data, Uh, Ultimately, they are also getting some basic input from which they are generating. Correct. So, this is what resolution 5.4 meters I mean the 5.8 meters of this of this four category Let me check. I have a document somewhere. which satellite and sensor you can just check-Okay.

you While you check that, sir, if I could just ask you on the funding side, So we are looking at a blended finance stack, which will change with phase one, phase two, phase three.

Like we want to start with... development finance and grants helping us pay the premium as well as the operation costs since margins will be low in the beginning. And slowly as the climate resilient practices are in full flow and our data subscriptions are in full flow, our insurance is in full flow, then our revenue will increase.

So the development finance can reduce and commercial investment can come in. So at this stage, do you think in space could be a potential space for funding or grants in phase one?

Mm-hmm.

Yeah, okay.

This, there is one fund I think was yesterday you also were mentioning, there is a technology adoption fund, right, EIF. In space funding, actually I will tell you what are the moderatives they have adopted so far. One is that they had opened up certain sectors. Saying that in this particular sector, like for example agriculture or urban or disaster or marine, they had a seed funding scheme funding scheme said that They can fund up to 1 crore.

with the equivalent funding from company side. So whatever, if company can fund 50, they will give 50 lakhs, but if company can fund 1 crore, they can give up to 1 crore. So, that is a seed funding scheme. So, there were some competitors who applied for that and they were selected under each of them, one agriculture and marine. I think they have said one or two to ten kind of thing they were done. Apart from that, they had started another, that is Technology Adoption Fund.

So many times, I mean, they might not have raised a particular topic, but if you have some idea, and you feel that something unique and niche you want to do, So, under that, then that proposal could be given to them where they could be giving funding. So, that is under TAF basically. So basically they are also in TAF, they will be looking for innovation which is currently not available such a product or scenario and process.

and yours is something unique which will have the potential scope market kind of thing. So, TAF could be one such option where possibly you can Apply. okay so there you have to what we have to focus is that how is the uniqueness because agree agree agree agree there are a lot of people who will be talking about every part So, and crop even resilience part also, but in that case why I was asking the specific questions in that only that yours is different and why in case something you are doing and you feel that's a uniqueBonne nuit, Jean.

But is it not that other people are not doing it because of some other constraints or they feel doing that doesn't help or whatever it is, that background study kind of thing. So all those highlights if you put it there will be a good amount of chance of And what is the procedure for this usually, sir? That I think because that entire booklet is given to the InSpace website. Go through that in case you have any problem with specific things I can check up and tell you.

This is given completely, there is a down, there is a brochure given for it here. and you can follow the process in case you feel that there is anything which you are not able to get a clarity Maybe I can connect to the right people so that we can bring clarity before you apply for that.

Absolutely.

Do you think for the pilot that we're talking about, do you think we could use TAF funds for that?

Okay, awesome.

I think that should be possible because TAF doesn't actually look for that you already have something, some company registered.

Can we apply for building the pilot?

I mean, all that is okay. I mean, they basically look for that. What is that? potential of the problem and scope of the solution in the overall market.

That was the other one.

Wheel check.

But DAF requires equal amount of funding, right? That's what you said?

No, not DAF. We had to check in the brochure what is that requirement. Okay, but seed funding was like one crore and And there are certain things I have seen in Tamil Nadu recently But they had some funding schemes for the startups.

And quite handsome funding was given like 50 lakhs and they had enough money to spend.

Okay.

I was a jury in that process. Thank you. In fact, not many We are actually to the level of getting it. Okay, and they had enough amount to be distributed that way but but the constraint was that The I mean the company should be registered in Tamil Nadu or they should have some linkage I mean, you can look for from such an angle also you can look for. I mean, for example, if you are looking for Maharashtra or AP or Karnataka, is there anything which...

makes a substantial difference for you Like I have seen one of the presentation there, they were in Nagaland or something like that. but they were trying to find out how they can make linkage with the Tamil Nadu and Rajesh or something so all that possibilities also you can look for Yeah.

Hmm.

Okay, maybe if you want I can connect you to that concerned person who handles Tamil Nadu. Long back when we were developing one product for village resource center, we had started one scheme. which they did not continue further village resource center that was it considered good but i mean thinking of higher ups at different level but different at different times so they didn't continue but that but it was a good scheme of village resource centers If there is any other state and anything else in this sort of scheme, you can connect us as well.

That would be very appreciated.

Yeah, there is a initial of who is the-I think deputy director of that in Tamil Nadu. And I'll give you contact. I mean, you can discuss also. I mean, you can get her possibly... some insight into how the state operate. Because one state does, other state want to repeat that if somebody something is done good. So Tamil Nadu has started that last year. And maybe Maaraft may see that model and may say, "Here's something we should start also here." So all these things can be repeated. So maybe you can get more information from him directly. How does this work and all.

If we are coming out of what we can do all that maybe we can also ask him.

And one thing sir, in the pilot stage we are, means there are three stages in it. One is now cast, then it is back test and then it is forecast. So for securing the funding for the pilot building prototype building. Currently we are at the backtest stage. So is it enough for going for the presentation for the funding or should we more, build it more.

We do have a little bit of the nowcast also building out. So I think backtest and nowcast by the time we go in for funding we will have substantial amount of work.

I think you need not have to go to very high level of DRL for TAF possibly. If you show that you are at TRL 3 or TRL 4, that may be fine with them. But the idea is that you should have a clear-cut idea of your plan. So somebody who is reviewing, he gets a confidence, yes, This team can really do and achieve what they are aiming for. People claim but they cannot achieve it because they don't have proper team or they don't have proper clarity into the whole problem So all that judgment when they do and review, they try to find out innovation, the team composition.

the problem and its demand as well as the feasibility of finally getting it up. Cool. Cool. So from that, the proposer should address all these points so that they get a confidence. Maybe when you start doing it, we can further talk. to refine it and make it more Uh... I mean, you know, shape that which will attract the attention of the reviewers also. Thank you.

right Yes, absolutely.

So just one point I wanted to ask you, since you mentioned that there are many companies that are in this space, of note that you know you liked like their business model or maybe their innovation anything that you liked and we should have a look Okay.

Mm-hmm. so i have not gone in details of uh i mean them i knew okay they are working in this particular field But they are not gone. We tell that what is their model. Some of them wanted to get facilitated from the IMD data.

No, thanks.

How do they get IMD data? I connected to them to IMD. In case you want to get connected to IMD, I can connect to them.

That would be very nice, sir. Okay. So...

I mean, ultimately there will be always some organizational issues or server issues, all those things could be there.

But they can be.

They can be tackled. I mean it could be a matter of one or two days or something like that. But all these things could be tackled over the period of time. Uh... But as I mentioned that backup strategies should always be there with you for any data. Suppose you are banging on one satellite and that satellite fails, how do you do? if you are banking on optical data alone how do you do with the SAR data then if you use SAR data Whether do you have experience for processing of the SAR data for the similar kind of objectives?

For example, many times, specifically from an agri point of view, typically when you get the data, that time you don't get it because of the cloudiness, cloudy or rainy or cloudy data. Number of days are very high. I mean, even it may not rain, but cloud could be there. So a lot of monsoon time getting optical data itself is a big problem. It's a big challenge. So SAR is one such an option where You are definite that you will get a data.

But in SAR methodology of processing the data is all the way different than the optical. So you must have that kind of We're building out those pipelines.

Yeah, that pipeline.

Keep in mind that part. Yeah, also Okay, sounds good, sir.

This is fine.

So, thank you so much.

I mean, it looks to be quite good. I am just trying to find out the company name. Just give me one minute. What is that that you like? Just you This is Hyderabad company only.

Wow. but they were at the starting level I don't think they have entered anywhere. Very deep. or they are not known as so.

Now, I think that chat has gone from my phone. Okay, maybe but I will come to I will message you. Okay. It will not help much but the field in which they were also operating was same. But also they were in more of a disaster point of view. Disaster agencies are the client. DME or Uh, They may have a little bit different umbrella also.

okay okay now all the inputs if i get i will whatsapp you and this name alsoUh. If you want that, I think possibly Tamil Nadu connection, I think maybe it's possible.

Would it be okay to maybe create a WhatsApp group?

Akshat, you were saying something?

Yeah, you can do. We can create so that we can share this.

That would be lovely. Yeah. Okay, awesome.

No good, I think. So happy to see that, I mean, because many of these ground level problems, engineers never think of.

Yeah. People are well aware about those kind of things. but typically this agri part and all is of course very much required but not many companies enter into this they don't get an idea that there is something which is which can be done here Seems very crucial. If you need any help from Maharashtra, Demorsant and all, I can connect with you.

Okay.

Awesome.

So, you personally, sir, or somebody that you know?

Yeah, I was actually director of that center so I know most of the people there. Whosoever has superannuated right now who are there I know.

I mean, I have superannuated so may not, they may not be able to help but in case you need anything, So are we able to get, I'm actually right now struggling with finding a Revenue circle or insurance unit like very granular yield data. I'm not able to find that. Going back to 2001, I'm able to find district level but it's useful to get granular data.

I think that circle wise, maybe if it is there at all, I doubt but district and Tysil wise it could be there.

Whatever I mean the most granular is would be amazing.

i have no doubt yield data may but if at all it is there it could be there only with this ms It might be. Otherwise, most of the other produce like Fasal, There was one breed called Fussel. There was a crop agrarian production estimation and Fussel. Fussel was the latter part of the Cape. Yes. So they had national level statistics, state level, district level. But all that was actually not 100% of a processing means we had a statistical estimation because you cannot before the harvest of the crop if you want to give a yield estimation Naturally 100% of the data processing would be possible.

So typically there is a stratification what would be done. So depending upon the previous historical data, you stratify the whole India into the different regions. Okay. Yield level, based on the yield level. and then get some sample data from each of them, a representative data, calculate the yield for them and then use statistical method to extrapolate to the test yield or district. Okay.

But there is no like specific like farm measurement yield data across the country I say? across the state. It doesn't happen like that. No, it doesn't happen like that. Okay. Will there be any suggestion, sir? Because it will be crucial to get the... I'm trying to get a weighted composite index for the insurance model. So in that, I can't do that unless I have granular data. Otherwise, I'll have to do a uniform weight for the whole district.

One of our main propositions on the insurance side is that we do plot level processing or block level processing as compared to PMF, PUI. So I don't know if you have any insight on that, how to get estimation for the yield for a granular area. .

If I am understanding you correctly, I mean just let us say if you use the 50,000 money 50,000 scale land use map for example. from NRSC 1:50,000 scale land use map you can get even 1:10,000 also you can get If you use the agriculture extract the only agriculture parts forgetting about the forest and other things let us say and based on that if you create a mask I'm not sure if your question is not very clear to me, but I thought just I could put bribe with that part.

That would help. I feel like, um, like there is a district level data I found in Maharashtra, right? So that gives me the exact tonnage or kilogram for like, let's say cotton, soybean, all of that stuff. So like that, if I can find something for a more granular, that would be ideal because then for each crop and each revenue circle, have a specific weightage given to each data feature. From my raw data, from my GEE and my ISRO data and IMD data, I will give a weightage to each variable, which will then calculate my composite index.

I think directly it may not be there but indirectly if we are able to make out from the available inputs because directly yield data is not there But this-Is this farm level? Farm level yield accounted somewhere in the government or so farm level what happens there there is a traditional method that they it is typically these local survey officers will note the crop production okay and then they will give final estimate based on their local each one of them basically reporting method it's a manual reporting method from the farm i see yeah i see they say this is my total production of this year for a let's say wheat or rice or whatever it is okay And second estimate comes from the remote sensing.

remote sensing also without knowing these reporting fevers based on the satellite data inputs like ISRO or Maharashtra remote sensing centers they have ways of finding out the yield like the state level or whatever it is The second part is coming because there will always be some mismatch in this. And the technical estimation. So I think PMFBY has done something but there has been recently they have found that agreed on the one particular solution where they will use both these figures and come out with the one figure.

which is agreeable on both sides. Maybe I will also, for that I will connect you to one of the agriculture specialists from Maharashtra. No, please. Scientist in agriculture in MRSF only. and he has been working with the PMFBY, he has been working on the more various agricultural projects.

Perfect sir, thank you so much.

You can also think of if you feel that it could be useful, he will be retiring this year. I like to keep the lead because many other times Super-annunciate people will be helpful in the business. So you can be an advisor or something like that if he is useful. But he has a lot of experience and he is well and very clear about that. Perfect. Whenever you want, I can connect with you. I mean, we can, need not set up a meeting. I mean, I can share the phone number.

You can talk to him.

Okay, so Okay.

Sounds good. Sounds good.

What I will do is form a group. Okay.

We form a group among ourselves. Maybe if you have some questions, you can fire there. I can give answers.

What happens in space has a mechanism that they feel how much interactions happened with the resident expert like i'm a resident but they also understand how much industries Taking the help of president experts. So they need to have that kind of feedback They don't stop anything but So they want every time that they should register and they should put a request on the InSpace portal like yesterday but you have done.

So that they know the amount of interaction that is happening.

and whether the scheme of this errand exporting useful or not for the industry or not.

Sounds good, though. Thank you so much.

Okay, awesome. Immediately, although we might have discussed something where to put it and then we show that okay in the meeting that it has been done.

Yes, this is very helpful, sir. Looking forward to staying in touch. Thank you. Thank you so much. Bye-bye.

Although some of the things we might discuss on the website.

Thank you. Oh, yeah.