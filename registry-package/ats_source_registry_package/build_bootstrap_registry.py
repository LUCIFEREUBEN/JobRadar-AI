import csv, os, re, json, zipfile
from collections import OrderedDict, Counter
from datetime import date

TODAY = '2026-09-22'
OUTDIR = '/mnt/data/ats_source_registry_package'
os.makedirs(OUTDIR, exist_ok=True)

FIELDS = [
    'entry_type','ats','company','board_token','token_type','hosted_board_url',
    'api_jobs_url','api_jobs_content_url','api_method','source_status',
    'source_checked_date','source_dataset','source_url','notes'
]

NOISE = {
    'api','app','apps','career','careers','company','companies','developer','developers',
    'docs','example','exampleco','examplecorp','example-corp','example-gmbh','foo','help',
    'jobs','j','search','slug','support','test','testing','www','acme','acme-corp','beta',
    'leverdemo','parseresume','patients','safety','applications','field','open-roles',
    'robots.txt','https:'
}

def clean_token(x):
    return (x or '').strip().strip('/').lower()

def valid_token(x):
    x=clean_token(x)
    return bool(x) and x not in NOISE and len(x) <= 220 and re.fullmatch(r'[a-z0-9._|:-]+', x) is not None

def provider_urls(ats, token):
    t=token
    if ats=='greenhouse':
        return (f'https://job-boards.greenhouse.io/{t}', f'https://boards-api.greenhouse.io/v1/boards/{t}/jobs', f'https://boards-api.greenhouse.io/v1/boards/{t}/jobs?content=true','GET','slug')
    if ats=='ashby':
        return (f'https://jobs.ashbyhq.com/{t}', f'https://api.ashbyhq.com/posting-api/job-board/{t}', f'https://api.ashbyhq.com/posting-api/job-board/{t}?includeCompensation=true','GET','slug')
    if ats=='lever':
        return (f'https://jobs.lever.co/{t}', f'https://api.lever.co/v0/postings/{t}?mode=json','', 'GET','slug')
    if ats=='workable':
        return (f'https://apply.workable.com/{t}/', f'https://apply.workable.com/api/v1/widget/accounts/{t}','', 'GET','slug')
    if ats=='smartrecruiters':
        return (f'https://jobs.smartrecruiters.com/{t}', f'https://api.smartrecruiters.com/v1/companies/{t}/postings','', 'GET','company_slug')
    if ats=='recruitee':
        return (f'https://{t}.recruitee.com', f'https://{t}.recruitee.com/api/offers/','', 'GET','subdomain')
    if ats=='teamtailor':
        return (f'https://{t}.teamtailor.com/jobs', f'https://{t}.teamtailor.com/jobs.json','', 'GET','subdomain')
    if ats=='breezy':
        return (f'https://{t}.breezy.hr', f'https://{t}.breezy.hr/json?verbose=true','', 'GET','subdomain')
    if ats=='personio':
        return (f'https://{t}.jobs.personio.de', f'https://{t}.jobs.personio.de/xml?language=en','', 'GET','subdomain')
    if ats=='rippling':
        return (f'https://ats.rippling.com/{t}/jobs', f'https://api.rippling.com/platform/api/ats/v1/board/{t}/jobs','', 'GET','board_slug')
    if ats=='pinpoint':
        return (f'https://{t}.pinpointhq.com', f'https://{t}.pinpointhq.com/postings.json','', 'GET','subdomain')
    if ats=='jobvite':
        return (f'https://jobs.jobvite.com/{t}', '', '', 'HTML','slug')
    if ats=='bamboohr':
        return (f'https://{t}.bamboohr.com/careers', f'https://{t}.bamboohr.com/careers/list','', 'GET','subdomain')
    if ats=='icims':
        return (f'https://careers-{t}.icims.com', f'https://careers-{t}.icims.com/sitemap.xml','', 'GET','subdomain_fragment')
    if ats=='workday':
        try:
            tenant, wd, site = t.split('|',2)
            host=f'{tenant}.{wd}.myworkdayjobs.com'
            return (f'https://{host}/{site}', f'https://{host}/wday/cxs/{tenant}/{site}/jobs','', 'POST','tenant|instance|site')
        except Exception:
            return ('','','','POST','tenant|instance|site')
    if ats=='paylocity':
        return (f'https://recruiting.paylocity.com/recruiting/jobs/All/{t}/','', '', 'HTML','tenant_guid')
    return ('','','','','slug')

rows = OrderedDict()
def add_row(ats, token, company=None, status='discovered_public_source', dataset='', source_url='', notes='', original=None):
    token=clean_token(token)
    if not token: return
    if not status.startswith('uploaded_') and not valid_token(token): return
    key=(ats,token)
    hosted, api, content_api, method, token_type = provider_urls(ats,token)
    r={k:'' for k in FIELDS}
    r.update({
        'entry_type':'board','ats':ats,'company':company or token,'board_token':token,
        'token_type':token_type,'hosted_board_url':hosted,'api_jobs_url':api,
        'api_jobs_content_url':content_api,'api_method':method,'source_status':status,
        'source_checked_date':TODAY,'source_dataset':dataset,'source_url':source_url,
        'notes':notes or ('Company label is board-token-derived; resolve from live board metadata.' if not company else '')
    })
    if original:
        for k in ['company','hosted_board_url','api_jobs_url','api_jobs_content_url','source_status','source_checked_date','source_url']:
            if original.get(k): r[k]=original[k]
        r['source_dataset']=dataset
        r['notes']=notes
    # Prefer uploaded rows / richer company names over slug-only rows.
    old=rows.get(key)
    if old is None or (old.get('company')==old.get('board_token') and r.get('company')!=r.get('board_token')) or status.startswith('uploaded_'):
        rows[key]=r

# 1) User-provided authoritative bootstrap files.
inputs=[('greenhouse','/mnt/data/greenhouse_board_tokens_7167-1.csv'),('ashby','/mnt/data/ashby_board_tokens_1662.csv')]
for ats,path in inputs:
    with open(path,newline='',encoding='utf-8-sig') as f:
        for rr in csv.DictReader(f):
            add_row(ats,rr.get('board_token'),rr.get('company'),f'uploaded_{rr.get("source_status","")}',os.path.basename(path),rr.get('source_url',''), 'Imported from the user-provided board-token registry.', rr)

# 2) Additional public slugs harvested from current public GitHub job/career data and ATS seed lists.
extra = {}
extra['lever'] = '''1password 3box accesssoftek accurate acme actian ada addi aechelon affirm agotai aircall ambrook anavationllc anduril ansatzcapital anthropic anyscale applied arbol artera-2 arturo astranis atlassian attest audius axiomzen babylonhealth backmarket belvederetrading bigblue binance blablacar blinkux boldbusiness bolt bosonai bosta bounteous brainnest brightedge brighthealthplan caseware celo centml cerebrae certik circleco close.io cloudnc codefights cohere contrastsecurity convoy coursera cred csit ctrl-labs datafox dave deepgenomics deloitte demiurgestudios despegar dragos droneseed duolingo edpuzzle egensolutions enthought eqbank ethereumfoundation etsy eventbrite evgo fanatics fieldnation figma finn.auto fullscript g2i galatea-associates gearset genbio geocomply-2 girlswhocode github goat goforward goldcast grandrounds hap-capital harmony hashicorp himama hotstar ideasunited immuta improbable intelliware invinity ironcladapp istaridigital.ai jina-ai jupiter kairosaerospace kaizenplatform karat kensho kikoff kitware klarna knewton kraken later ledn limebike loadsmart loft lyft magnetforensics mashgin mbrdna meesho mistral mokapos neeva netomi neuron7 nextbigsound nibiru nimblerx ninjavan nium octoenergy offchainlabs onefootball oowlish openai overbond pagerduty palantir pilot pioneer-services pointclickcare prelay protocol quantcast qubole quizlet-2 rainforest redcanary relativity returntocorp rimeto rivosinc s4n saronic scaleai scrapinghub secureframe selfmade sendinblue shopback-2 shyftlabs sighten sisu sonatype spotify stellar stubhubholdings super-com supermove swissborg sylndr teleport telesat tesorio tfgco thinkahead thrive tophat trailofbits tramgroup tri truora twitch ushur verdigris verkada vivacitylabs voltrondata waabi wealthfinancialtechnologies wealthsimple weride whereby wish wisk wolt woven-by-toyota woven-planet-2 x1creditcard yelp zeneducate zoox'''.split()
extra['workable'] = '''advantmed al-warren-oil-company-inc albelli-photoboxgroup alloy-automation altom-transport apna argenthq atb-financial avantstay awesomemotive axiomsl balena betterview bizagi bluechip-financial blueground blueskyhq boostdraft camaloon capula-investment-management-ltd carbmanager carbonplan careacross cartegraph centaur-analytics-inc channel-factory chargify clarity-ai classcraft clearpayeu climaterobotics cliniko cogna connectprep cti-jobs datatonic datavisor-jobs deepset definedcrowd-corporation demystdata dextra divio dnsfilter docplanner dodge-construction-network double-eleven dscovr elementio elevate-semiconductor eluvio evolv-technology exoticca feeldco flawless-ai flexion-robotics flowith flowxai forbes-media freelancer genetec-inc getbits gomining gravitysketch greenzone-solutions-inc hades hicx-solutions hospitable huggingface huzzle hydrosat hyperlight hyperverge imachines imandra innopeaktech intellectsoft io-global ionenergy isentia jobgether lahaus languagewire later-5 leadtech lifebit-biotech-ltd liqwid-labs lockrose-limited luminance-1 lunit marketgoo mercari mercier-consultancy mila-2 mind-friend mlabs movement-labs multimediallc murmuration mytutor nectafy nexusstudios ocean-os oliva1 our-future-health payabl peachpay perryhomes platzi plentific plumerai pony-dot-ai pravaler-1 praytell prenda pronexus-1 qodea quadible quadric-dot-i-o-inc quantumloopai remotebase rendered-ai responsiveads-inc retinai reversinglabs revunit-1 robusta rollbar rubikal salescaptain salla sastrify sintra sithswap skrapp skygig skylabs-ai skylight smartnews somerce stackbuilders stockbit storyteq studiogobo subscript swim sylvera tagaddod tarte-inc terminal49 teserac-inc the-metaplex-foundation tiger-analytics tmeic-corporation-americas toloka-ai transmarket-operations-llc troop-1 twgai tymit unacademy ununuzi-consulting-s-dot-l uplearn uptime-dot-c-om usealbatross uzabase-inc valsoft-corp venntro very-good-ventures visenze vontive wallbox wallstreetquants western-magnetics withplum yoti zinc-labs-inc zkx 1000heads abzorbagames antarcticaglobal arkadium-1 carry1st clockwork-labs cloudhire1 coherence dblstallion digital-waffle-2 drest electric-square elevation-capital-3 euromonitor followloop gamesquare gamigo gig-6 goreel gram-games heavy-iron-studios hike hutch hypemasters imagine-io impact-theory infinitereality jackbox-games jellyfish-pictures-ltd junglee-games kokku-games lighthousegames liquidadvertising localsoft-sl logifuture modio moonbug-entertainment motorsport-games ndreams newrich-network nextgen-clearing novomatic owlchemy-labs payload-studios powtoon secret-6 snowed-in-studios-3 space-ape-games spectarium sperasoft square-enix stick-sports stream-hatchet team-17-digital testronic twocircles unit9-ltd universally-speaking unseen-inc we-are-social-1 wushu-studios zeptolab zipdev'''.split()
extra['smartrecruiters'] = '''10times a44games abbott abgames accor accuratebackground acldigital adidas adiresourcing adpushup advantagesolutions afry agency09 agileengine airlabinc alegrium1 alphamedia alten amvadev1 applicantz arhs aristanetworks arkavis arrible arthrex assistsoftware assystem atidantechnologies avacendinc axelspringernewsmedianational babilgames baxenergy bcforward believe betacrafttechnologies beyondinc bitlane blackkitestudios blend360 blockville blocresources blueislestudios bluewiresoftware bookerdimaio bootloaderstudio bosch boschgroup brainhunter buckeyebroadband buildstaffinc bytedance caci canva caterpillarinc cdprojektred chimeratechnologies citi cityofphiladelphia citystateentertainmentllc clearpointrecruitment comcastcorporation continental creativecoveinc danone dataiku datastaffinc datatobiz daxko1 dentsu devoteam divensi1 docusign dontnod dotsoftsa drpanda dungarvin dxmindsinnovationlabspvtltd ekosystem elevatek-12 endava epochgames espressifsystems essilorluxottica ettaingroup evolution evsinc ewargames experian experthiring exponentiaai federalsoftsystemsinc filmless finmo firehosegames flaanaa fourseasonshotelsandresorts fracturedbyte freshboxmediapvtltd freshworks fundamentallygames funguystudiophilippinesinc futransolutions futuremug futurumtechnologyltd galaxesolutions game5mobile gamecloudtechnologiespvtltd gameloft gamesforlove gearinc geico genea generagames1 giantsoftwaregmbh gloify gluckgames gmsservices govini grab hackajob hackerrank harbingergroup hardballgames heartmachine hermes hitachisolutions hive1 howardhannarealestateservices hoyoverse hp ikea informaGroupPlc informicasolutions innovecs insightsoftware intel intelerad intergalacticgamingltd intersourcesinc interviewkickstart intrepidstudios inxiteout iodigital ironbellystudios jadeglobal jammedia jellyfish1 jsheldllc jti k-group1 kantegroup kenvue keylentinc keywordsaustralia knackstudios kodo konecranes kovaico kronospan lecollectionist letsgetchecked levelall lightwonder lincolndigitalgroup linkedin3 llnl locumtenenscom loft17visuals lonza loral loreal lottiefiles lumengames mattelinc mcdonalds mcdonaldscorporation meta4 mgmresortsinternational miraclesoftwaresystem1 miratech1 missionboxsolutions mitratech mixmob mnrsolutionspvtltd mottmacdonald movingpicturecompany movingwallsindiapvtltd mpowerfinancing nagarro1 namely nbcuniversal3 nestle netradyne netskope newrelic nextlevelbusinessservicesinc2 nielseniq nine nopadvancellp novomatictechnologiespoland nvizziocreations odysseyinteractive oldskullgames1 opensystemstechnologies oxbridgeinternationalschool pacificacontinental paloaltonetworks2 peoplecanfly pepsico personiv pharmaace philipmorrisinternational play-perfect playtech playwing publicisgroupe purview ramboll3 rdsdigital realitygames rebelfoods recruitrix redpointlabs redpoints1 renesaselectronics resmed revalsystechnologies rosettagaming ryseupstudios schneiderelectric secondtalent segulatechnologies servicenow shopify siemens sigmasoftware2 signalspacelab sikaag silentgames skeletonkey skyrocketventures smartrecruiters softsuavetechnologies speedlabs sportradar spotify springernature starkflow starmarketing starschema stonesearch stratacent symphonyai synergyresourcesolutions syngentagroup t-systemsictindiapvtltd1 talentfolks talentsocio talentsoftwareservices talentxo tatsuworks teampumpkin techarmyllc techlandsa technicolorcreativestudios technicolorgroup technorizensoftwaresolution techstargroup techvedika tempo ten4 themill2 therankgroup tonicdna1 uber ubisoft2 unbrokenstudios unifynd untoldtalesSA ursusinc valkyrieentertainment valu1 valuelabs veremark verisk version1 visa vizexperts vmdcorp volksbyte wayfair wayforwardtechnologies wayup westerndigital whatfix whizzhr wildbrain xiaomiindia xpologistics yggdrasilsandbox abbvie aboutyougmbh abstrabittechnologiespvtltd accenturefederalservices acumatica aerovect afficiency agtechnologies1 ajnainfotech approvalmaxlimited assent barkbackllc blinqlabs canadianbanknotecompany captechconsulting cern chainsafesystemsinc clinicalink codeage collabera2 cppinvestmentsinvestissementsrpc crowninnovationsinc customshow datazymes dellfortechnologies devex1 egisgroup encephaloinvestments entain eurofins eversana1 fintricity fireeyeinc1 hirevue houseofgigs huaweitechnologiescanadacoltd huckadventures ifs1 inbulkscorp infinitequant informagroupplc inmarsat integratedresourcesinc interco intuitive jacklinksproteinsnacks kioxia kostalgroup kvytechnology leger2 linuxfoundation luxemediallc mandiant marinerpartnersinc microstrategy1 mirantis ncs3 netcompany1 nextstepsystems ni northwesternmutual oneclick-ui paconsulting prosidianconsulting pubmatic purpleboxinc regdeskinc renaissance reporterscommitteeforfreedomofthepress ridicorp rrsgroup sajixsoftwaresolutionprivatelimited sandisk scalablegmbh sia sightcall smithsgroup2 socotecukireland solidigm soprasteria1 spaceknowinc square sr-jobs swgroup tessel thenielsencompany truenhealthanalyticsanibmcompany ttp1 tuftsmedicalcenter1 universityhealthnetwork veoliaenvironnementsa vwhcapitalmanagementlp wavestone1 wellmarkinc wise wiser wish zscaler'''.lower().split()
extra['recruitee'] = '''11bitstudios atlys bettercollective chaos chimpworks crazygames focusentertainment focushomeinteractive futureworks gainpro grid huuuge illuvium immersionspzoo lucidgames mitsogo pixelpool playtestcloud propel realitygames rubygamestudio spocket squeezestudio tensquaregames trackman universegroup villagetalkies wonderkind 1x aerolab aikidosecurity analystinstitute antire aquablu ascendingai attendi authenteq auxolar baz bemind betterplaceorg bigcartel birdeatsbug bitfinex bossabox cainwattersassociates causalens centreon chargify claranetitalia comnovogmbh cscfi dataforce ddx deck dentalxrai doclerholding dsquares faktionbv1 ferryhopper flextrade foreignpolicy gain gastrofix graphcms greatminds growprogress groww hectorkitchen holded hostaway huaweicanada ignusdigital incognia infoprolearning innodatainc interbrandsorbico ironhack kayrros1 kestrelfreight kigroup lenskartcareers lleverage logiqs makerdao makersitegmbh matera medecinssansfrontiereswaca meisterwerk mesosolutions metr metyisag mgid mobilexpense monstarlab msf netdata nextaillabs ngxinteractive nicolab1 ocasta on2it opengovernmentproducts parfumado payflows pix recharge remerge republichr riscure rise riverflex salzburgglobalseminar secondspectrum superlist synapseanalytics tbibankro tensortechnologies tether thelandbankinggroup tiugotech trustedshops upside upvestco werkenbijbrandnewday whalebone xchange zeotap zerofy zomato'''.split()
extra['teamtailor'] = '''awaceb axolotgamesab cigames everymatrix fitxr-1642768457 gigglebug goodgamestudios graviteetopcoltd hampastudio hypehype kavalrigames passivelogic pixiongames pushgaming rawpowergames-1700833558 softswiss sybo tacticaladventures tanglewoodgameslive-1744291072 veoneerin zaibatsuinteractiveoy again akality ampersandelectricmobility antaretechnology-1748341798 aria-jobs axmed barbri bezerocarbon bryter bunnynet capraconsulting castai centra chip clearroute cloudnine clovrlabs coinflex creai.na crossmint.na deezer dektech diffuselycompte-1738823875 digisapsolutions ecoonline emeria erlangsolutions ernicareersph evenergy flightstory flower fortnoxab fyndiq heydata hiire huaweifinlandrnd huaweiireland huaweiresearchcentergermanyaustria huaweiuk interruptlabs itiviti klarnagroup legl-1684858710 lendurai media.cdn multiversecomputing netronix nexar-1702298813 nexergroup noda-1720000970 outfitterygmbh partnerd polestar producthackers progressbypeople pulpomatic rebtel redegal rubycentral saasglobal saasglobal-termly sisugroup softwarefinder.na spacelift sweep swissas synthesized tibber tooploox tramcase.na typeoneenergy unleash unobravo upskilldigital veed vincitoyj wakapi wiser xpertai'''.split()
extra['breezy'] = '''20four7va 47-degrees accrete-ai adwerx antithesis arena-club avail awarri bear-robotics binary-star brainscape ca-office-of-digital-innovation canoo centrifuge city-report-inc civey code-states codeverse coinroutes-inc combient cove crewscope crowdbotics-corp datamaxis decent deep-ivy-ltd dex-labs disco earl-hardy eigroup etiqa-srl formlogic freeeup fy gastronomous-technologies-inc gesture-us-inc givecampus gravitational gsmc guusto hyspeciq iff infinyon internet-freedom-foundation intramotev-autonomous-rail invisible-technologies ivisa jro-ventures kabuni lemonade-technology-inc lethub linode llamaindex ltg lufco matroid maxab milu-health nalpeiron-inc nationsbenefits navaide netsync-network-solutions nexthire ninjaholdings ninjas-code onebridge pactsafe-inc pagefreezer-software-inc passport pdmi pixieset polarsync politech product-hunt prozis q-block-computing quansight rabbitmart requis reveleer sdsn-youth setter sherpany shiphero sigma-computing solugen sortlist sortly-inc sounding-board-inc stack-influence stoss-inc superrare swipejobs telespazio-be textile the-graph the-henry-ford the-looma-project the-qt-company total-life-inc-1 travelnest usemultiplier utxo-ltd vagaro veeqo-ltd vericode vetsez vigilant wolf-games yardiromania zetier'''.split()
extra['personio'] = '''1komma5grad 1nce adsquare agile-robots alephalpha apheris appliedai autarcenergy banxware building-radar capmo caravelo casavi celonis cip-marketing-gmbh circus cleanhub contracthero-gmbh deepl deepset e-mobil-bw-gmbh elli envelio eraneos flix freeletics gamescoin gemma gesis geton giant-swarm gridx hairoboticseurope hakuna holidaycheck holidaypirates holidu holoplot htgf hypcloud intrafind-software-ag isaraerospace jtl-software-gmbh jucr-gmbh juna-ai krisenchat lightcurve liveeo-gmbh luminovo m4c merantix mona mostly-ai mrge-group-gmbh nextlevelcommerce penzilla-gmbh personio planetafoods polyteia proveg q-energy raisin redalpine ride scalable scalian-germany serlo shyftplan snapview solytic speckle spread-gmbh sunvigo tacto temedica thinkport-gmbh thinksurance-gmbh tng tonies valuedesk vida-place visionai vivid vmray-gmbh wire-1 workist-gmbh xayn'''.split()
extra['rippling'] = '''4ag 7factor-software aalyria-careers absencesoft accelerant accelintjobboardtest acretrader-jobs agilitypr ai2io aitp ampersand-biomedicines apexanalytix-careers armada-careers bayrock-labs bizzycar bloomgrowth blue-robotics bonsairoboticsmain boom-supersonic brevian-careers briowt campspot capacity cargosprint chess class-3-technologies-inc colheli collieraerospace corva cozey-internships createmusicgroup curve-dental d-wave-quantum democratic-national-committee denari dialogue-en dialogue-fr dropzone-ai duku-ai dynamo-ai edgehog-trading eridu-ai etg fello-careers flatiron-school flexai fluidai-medical-careers flybits formant-careers foundation-robotics gitar-careers greengas gtp-software-inc holly incredible-health just-appraised-jobs knotch-inc koreai-india-careers lightguide loop-careers luma-financial-technologies lynx-software-technologies mission-underwriting-services momentumcareers moon msm mykaarma naxo neo-financial neosigma netwrix-corporation north-cloud nutrient oneorigin onware orderco outsmart packetlabs pendulum-intelligence-jobs planhub-inc pythian rearc rev-robotics reverb-careers rippling rugsusa sdl solv-health spreeai stag-careers studyfetch teamworks-careers theguarantors-open-positions tiledb-careers tive-careers uhin-careers veefriends-llc veracityinsurance-careers zapata-quantum zuckerman-investment-group'''.split()
extra['pinpoint'] = '''accenture appquantum ardentprinciples astrolab cfc coforma confluence cottonholdings cuvva db1group deepseas digitalscience enablemedicine enosisbd epuki everi exclaimer gentrack harnham hazelcast idtus impulsespace intermedia knack made-tech magic naimaudio napier nasstar precisionneuro premier-roofing premierleague rewardgateway sabio safetywing smartthings surrealdb tabby turionspace whiteswandata wolve workwithus xantura xeneta youlend'''.split()
extra['jobvite'] = '''aarete actionet actionet-review alienvault altamiracorps ashoka asus biofiredx blizzard bpbcareers chobani cirruslogic citco clearpath confluent crossover-health crowdstrike curriculumassociates dotdash egnyte elire emoneyadvisor-review exabeam fieldcore fingerpaint fiverings ghx gresearch iboss idtus inogen internetbrands isoftstone jumio-corporation justicedigitalandtechnology laserfiche leantechio leovegas liferay litera livevox logitech mcclatchy metropolitantransportationauthority neogenomics ness newyork-public-radio nexcess ninjaone noventiq nutanix ovt paloaltonetworks pandora pingidentitycareers pointofrental pragmaticplay progress rackspace retailmenot revlocal saama servicenow shutterfly shutterflyinc silabs simaai spectralogic spireon splunk splunk-careers src-inc sugarcrm techsmith the-climate-corporation trustwave tylertech varonis-internal veeva verifone viking-cloud visionist wavecomp-ai webmd windriver wri zappos zscaler zynga'''.split()

source_for = {
 'lever':'GitHub code-search harvest + public ATS lists',
 'workable':'GitHub code-search harvest + Tindi12/Scout public ATS list',
 'smartrecruiters':'Tindi12/Scout public ATS list + GitHub code-search harvest',
 'recruitee':'Tindi12/Scout public ATS list + GitHub code-search harvest',
 'teamtailor':'Tindi12/Scout public ATS list + GitHub code-search harvest',
 'breezy':'GitHub code-search harvest', 'personio':'GitHub code-search harvest',
 'rippling':'GitHub code-search harvest','pinpoint':'GitHub code-search harvest','jobvite':'GitHub code-search harvest'
}
for ats,tokens in extra.items():
    for tok in tokens:
        add_row(ats,tok,status='public_seed_unverified',dataset=source_for[ats],source_url='https://github.com/',notes='Publicly observed ATS tenant/board token. Validate live status during crawler execution.')

# Manually verified Africa-focused ATS directory entries (small, curated source).
africa_verified = {
 'greenhouse': [('GiveDirectly','givedirectly','active','KE'),('Girl Effect','girleffect','active','KE'),('Educate!','educate','watchlist','UG'),('Paystack','paystack','watchlist','NG'),('Moniepoint','moniepoint','watchlist','NG'),('OfferZen','offerzen','watchlist','ZA'),('ALX','alxafrica','active','KE')],
 'lever': [('KOKO Networks','kokonetworks','active','KE'),('Tala','tala','active','KE'),('Binance','binance','watchlist','NG')],
 'ashby': [('M-KOPA','m-kopa','active','KE'),('Talent Safari','talentsafari','active','KE')],
 'smartrecruiters': [('Visa','visa','active','KE'),('Watu Credit','watucredit','active','KE'),('Amref Health Africa','amrefhealthafrica','active','KE'),('Digital Divide Data','digitaldividedata','active','KE')],
 'workable': [('Inkomoko','inkomoko','active','KE'),('Kwara','kwara','watchlist','NG'),('Flare','flare','active','KE'),('Welcome Tomorrow','welcometomorrow','active','KE'),('Kentro','kentro','active','KE')],
}
for ats,items in africa_verified.items():
    for company,tok,st,country in items:
        add_row(ats,tok,company=company,status=f'africa_directory_{st}',dataset='Thelastpoet/africa-ats-directory',source_url='https://github.com/Thelastpoet/africa-ats-directory',notes=f'Curated Africa ATS directory; country={country}; source status={st}. Revalidate live status during crawl.')

# 3) Upstream provider directories: these are the canonical expansion sources for the full builder.
directories = [
 ('greenhouse','8333','https://raw.githubusercontent.com/Feashliaa/job-board-aggregator/main/data/greenhouse_companies.json','Feashliaa/job-board-aggregator','Flat JSON array of Greenhouse board slugs; Common-Crawl-derived public ATS directory.'),
 ('ashby','3161','https://raw.githubusercontent.com/Feashliaa/job-board-aggregator/main/data/ashby_companies.json','Feashliaa/job-board-aggregator','Flat JSON array of Ashby board slugs.'),
 ('lever','4368','https://raw.githubusercontent.com/Feashliaa/job-board-aggregator/main/data/lever_companies.json','Feashliaa/job-board-aggregator','Flat JSON array of Lever account slugs.'),
 ('workday','12884','https://raw.githubusercontent.com/Feashliaa/job-board-aggregator/main/data/workday_companies.json','Feashliaa/job-board-aggregator','Compound tokens tenant|wd-instance|site.'),
 ('bamboohr','11316','https://raw.githubusercontent.com/Feashliaa/job-board-aggregator/main/data/bamboohr_companies.json','Feashliaa/job-board-aggregator','Flat JSON array of BambooHR subdomains.'),
 ('icims','10108','https://raw.githubusercontent.com/Feashliaa/job-board-aggregator/main/data/icims_companies.json','Feashliaa/job-board-aggregator','Flat JSON array of iCIMS careers subdomain fragments.'),
 ('paylocity','','https://raw.githubusercontent.com/Feashliaa/job-board-aggregator/main/data/paylocity_companies_clean.json','Feashliaa/job-board-aggregator','JSON objects containing Paylocity tenant GUID, company name and job metadata.'),
 ('workable','2756','https://raw.githubusercontent.com/Infrasity-Labs/developer-marketing-jobs/main/discovered_workable_companies.json','Infrasity-Labs/developer-marketing-jobs','Object with companies[] of Workable account slugs.'),
 ('smartrecruiters','308','https://raw.githubusercontent.com/Tindi12/Scout/main/packages/api/data/smartrecruiters_companies.json','Tindi12/Scout','Flat JSON array of SmartRecruiters company identifiers.'),
 ('recruitee','28','https://raw.githubusercontent.com/Tindi12/Scout/main/packages/api/data/recruitee_companies.json','Tindi12/Scout','Flat JSON array of Recruitee subdomains.'),
 ('teamtailor','21','https://raw.githubusercontent.com/Tindi12/Scout/main/packages/api/data/teamtailor_companies.json','Tindi12/Scout','Flat JSON array of Teamtailor subdomains.'),
 ('multi','12144','https://raw.githubusercontent.com/outscal/OpenJobs/main/data/companies_v2.json','outscal/OpenJobs','Company corpus with ats_links; use regex extraction to discover Greenhouse, Lever, Ashby, Workable, SmartRecruiters, Workday, Teamtailor, Recruitee, Personio, Breezy, BambooHR, Jobvite and Join.com tenants.'),
 ('multi','21','https://raw.githubusercontent.com/Thelastpoet/africa-ats-directory/main/companies/index.json','Thelastpoet/africa-ats-directory','Curated Africa ATS directory with verified/watchlist metadata across multiple providers.')
]

with open(os.path.join(OUTDIR,'provider_directories.csv'),'w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=['ats','known_entry_count','dataset_url','source_dataset','notes'])
    w.writeheader()
    for d in directories:
        w.writerow(dict(zip(w.fieldnames,d)))

# Add directory rows to the master registry so a runtime loader can expand them.
master_rows=list(rows.values())
for ats,count,url,ds,notes in directories:
    r={k:'' for k in FIELDS}
    r.update({'entry_type':'directory','ats':ats,'company':ds,'board_token':'','token_type':'directory_url',
              'source_status':'directory_to_expand','source_checked_date':TODAY,'source_dataset':ds,
              'source_url':url,'notes':f'{notes} Known snapshot count: {count or "not stated"}.'})
    master_rows.append(r)

# Sort board rows by ATS/token, then directories last.
master_rows.sort(key=lambda r:(r['entry_type']!='board', r['ats'], r['board_token'], r['company']))

master_path=os.path.join(OUTDIR,'ats_source_registry_bootstrap.csv')
with open(master_path,'w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=FIELDS)
    w.writeheader(); w.writerows(master_rows)

# Separate per-provider bootstrap CSVs.
providers=sorted({r['ats'] for r in master_rows if r['ats'] not in ('multi','')})
for ats in providers:
    rs=[r for r in master_rows if r['ats']==ats]
    with open(os.path.join(OUTDIR,f'{ats}_source_registry.csv'),'w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=FIELDS); w.writeheader(); w.writerows(rs)

# Summary.
board_counts=Counter(r['ats'] for r in master_rows if r['entry_type']=='board')
dir_counts=Counter(r['ats'] for r in master_rows if r['entry_type']=='directory')
summary={'generated_on':TODAY,'board_rows':sum(board_counts.values()),'directory_rows':sum(dir_counts.values()),'board_rows_by_ats':dict(sorted(board_counts.items())),'directory_rows_by_ats':dict(sorted(dir_counts.items())),'notes':'Board rows are bootstrap seeds. Directory rows are expanded by build_full_registry.py on an internet-connected runner.'}
with open(os.path.join(OUTDIR,'registry_summary.json'),'w',encoding='utf-8') as f: json.dump(summary,f,indent=2)
print(json.dumps(summary,indent=2))
