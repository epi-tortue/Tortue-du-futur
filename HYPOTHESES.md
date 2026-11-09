# Hypothèses chiffrées hors documentation

Ce fichier liste chaque valeur de `config.yaml` ou `risks.yaml` qui ne vient ni de la doc Epi'Tortue
(https://epi-tortue.github.io/docs/), ni de la coque Testa (https://github.com/epi-tortue/Testa), ni d'une source de
données citée. Chaque valeur est accompagnée de sa justification. Les identifiants `[Hxx]` sont repris en
commentaire dans les fichiers de configuration.

**Rappel** : le simulateur produit un *scénario plausible* et une *statistique d'issues*, pas une prédiction.
Les valeurs marquées *jugement* sont les premières à remettre en question.

## Mission et données

| Id | Hypothèse | Valeur | Justification |
|---|---|---|---|
| H01 | Point de largage | 47,0°N 48,0°W | Règlement Microtransat, règle D.4 : au moins 40 nm d'approche autonome avant la ligne de départ Ouest (48°N–45,5°N par 47°W). À 47°N, le méridien 48°W est à 40,9 nm de la ligne. Choix validé par l'utilisateur (option A1). |
| H02 | Centre du cercle d'arrivée | 52,0°N 16,0°W, rayon 25 km | Règle D.1 : cercle de 25 km choisi par l'équipe sur la ligne Est. On prend le segment 55°N–51°N par 16°W, à l'ouest de l'Irlande, en cohérence avec S19 (« router au nord »). L'orthodromie depuis le largage fait 1 272 nm, et non 2 700 nm : ce dernier chiffre est la distance parcourue par SB Met. |
| H03 | Cellules marines sans valeur (terre) | valeur de la cellule marine la plus proche | Open-Meteo Marine ne renvoie rien sur terre. Seules les mailles côtières de l'interpolation sont concernées. Le nombre de cellules remplies est noté dans `data/meta.json`. |
| H04 | Courant | `ocean_current_velocity/direction` d'Open-Meteo, sans dérive de Stokes ajoutée | Le produit SMOC (Mercator) inclut déjà la marée et la dérive de Stokes : ajouter un terme de dérive due aux vagues ferait double emploi. |
| H05 | Résolution | grille 2° (42–58°N, 56–8°W), puis couloir à 1° | Quota gratuit Open-Meteo d'environ 10 000 appels pondérés par jour. Les champs ERA5 sont à 0,25° et les champs marins plus fins encore : à 1° ou 2°, fronts et tourbillons sont lissés, ce qui sous-estime probablement les extrêmes locaux. Avec une grille de 2°, chaque nœud capte la valeur ponctuelle d'un tourbillon, d'où des courants localement incohérents. |
| H06 | Pêche | effort de pêche apparent GFW (AIS), mensuel, agrégé à 0,5° | Ne voit que les navires équipés d'AIS. Les petits pêcheurs côtiers sont sous-représentés, donc les rencontres près des côtes sont probablement sous-estimées. |
| H07 | Trafic commercial | présence AIS GFW, `vessel_type in ('cargo','tanker')` | Densité moyenne de navires, pas des routes. |
| H08 | Icebergs | non simulés par défaut | La base d'observations de l'International Ice Patrol (NSIDC G00807) demande un compte Earthdata, et rien ne garantit que la saison 2026 y soit déjà. On n'invente pas de données : le module ne s'active que si un fichier `data/icebergs.csv` est fourni. |

## Bateau

| Id | Hypothèse | Valeur | Justification |
|---|---|---|---|
| H10 | Résistance de carène | formules de Testa (`coque/propulsion.py`) : ITTC-57, Watanabe, vague forfaitaire | Reproduit Testa à 1,60 Wh/km à 1 m/s, hors fardage (vérifié par test). La valeur de 40 W à 1,5 m/s supposée au départ est remplacée par la polaire réelle de la coque : 21 W à 1,5 m/s. |
| H11 | Rendements | hélice 0,50 × chaîne 0,85 | Paramètres `RENDEMENT_PROP` et `RENDEMENT_CHAINE` de Testa. |
| H12 | Puissance moteur maximale et hélice | 60 W, Ø 0,15 m | Jugement. Le diamètre limite la poussée statique (théorie de quantité de mouvement) quand le bateau est presque arrêté par vent de face. |
| H13 | Résistance ajoutée par les vagues | k·g(α)·Hs², calée pour diviser par 2 la vitesse de 1,5 m/s par Hs = 4 m de face ; g = 1 de face, 0,6 de travers, 0,2 de l'arrière | Jugement d'ordre de grandeur pour un engin de 2 m. Testa ne modélise que l'eau calme. |
| H14 | Fardage | surface frontale 0,15 m² (Cd 0,8), latérale 0,70 m² (Cd 1,0) ; surface latérale immergée 0,27 m² (Cd 1,0) | Estimé depuis les dimensions de Testa : largeur 0,38 m, hauteur émergée environ 0,40 m, francbord 0,20 m, pont bombé, tirant d'eau 0,14 m. Moteur coupé, il en résulte une dérive d'environ 3,8 % du vent, l'ordre de grandeur d'un radeau sans quille. |
| H15 | Encrassement (biofouling) | frottement +5 %/mois, ×3 au-dessus de 18 °C ; panneaux −20 % par unité d'encrassement (plancher 50 %) | La doc reste qualitative (« semaines », « quelques mois »). Jugement. |
| H16 | Température de la batterie | T_bat → SST + 2 °C, avec une constante de temps de 2,8 h | Batterie plaquée au fond de coque (S1 : masses lourdes au fond), d'où un couplage à l'eau. +2 °C pour les pertes internes. Scénario B1 choisi par l'utilisateur. |
| H17 | Chauffage de la batterie (scénario B2) | 10 W maximum, consigne 6 °C, conductance 0,8 W/K, capacité thermique 8 kJ/K | Boîtier isolé d'environ 3 cm de mousse, 8 kg de cellules. Les deux scénarios sont simulés (`python main.py chauffage`). |
| H18 | Vent à hauteur de pont | 0,72 × U10 | Profil logarithmique U(0,5 m)/U(10 m) avec une rugosité de mer z0 = 2·10⁻⁴ m. |
| H19 | Puissance crête | 1,365 m² × 200 W/m² = 273 Wc | Surface de cellules de Testa × un rendement de 20 % pour des panneaux flexibles. La doc vise 250 Wc. |
| H20 | Charge à froid | interdite sous 0 °C, limitée à 0,1 C entre 0 et 5 °C, 0,5 C au-dessus ; rendements de 0,97 en charge et 0,98 en décharge | Doc P11 pour le seuil de 0 °C et la marge à +5 °C. La limite de 0,1 C et les rendements sont des valeurs usuelles des fiches LiFePO4. |
| H21 | Répartition des 114 Wh/jour | calculateur et capteurs 2,5 W, Iridium 0,5 W, AIS et feu 1,0 W, divers 0,75 W | Le total vient de la doc ; la répartition est un jugement. Elle sert au délestage. |
| H22 | Rayonnement ERA5 | lu à t + 30 min | Open-Meteo donne le rayonnement moyen de l'heure précédente. |
| H23 | Moteur coupé | le bateau se met en travers au vent | Coque sans quille, pod à l'arrière. |
| H24 | Gestion d'énergie S8 | `validée` : moteur = production moyenne sur 24 h − consommation de bord + (SOC − 0,6)·C/24 h, délestage à 25 % et 15 % ; `partielle` : paliers de SOC ; `absente` : 21 W constants jusqu'à la coupure du BMS, redémarrage à 10 % | La doc demande délestage puis dérive, sans chiffres. Seuils inventés et configurables. |

## Navigation et estimation Codac

| Id | Hypothèse | Valeur | Justification |
|---|---|---|---|
| H30 | Vitesse surface | v ∈ v_nom(P)·[1 − 0,5 ; 1 + 0,1] | Sans loch, v_nom est la vitesse en eau calme donnée par la polaire pour la puissance commandée. La borne basse est large parce que le vent et les vagues ne peuvent que ralentir le bateau. |
| H31 | « Dérive » d | d̂ estimée sur une fenêtre glissante de 2 h de fix acceptés ; δ = 0,7 m/s + 0,03 m/s par heure sans fix + \|v_nom − v_nom moyen\| + 0,15 m/s au passage moteur en marche ↔ arrêt + v·(changement de cap) ; δ maximal (1,5 m/s) tant que d̂ n'est pas estimée ou après une coupure de plus d'une heure | Calibré par essais sur la météo réelle : **0 sortie de boîte sur plus de 100 000 pas sans saut de GPS** (tests `test_vraie_position_toujours_dans_la_boite_sans_saut`). Avec δ = 0,15 m/s, 20 % des pas sortaient de la boîte ; avec 0,3 m/s, 2 % ; avec 0,5 m/s, 0,35 %. Contrepartie : sans GPS, la boîte grandit d'environ 4 km par demi-heure. |
| H32 | Biais du compas | après détection, les bornes de cap sont élargies de ±30° ; le compas est déclaré HS après 18 incohérences | Les petits biais constants sont absorbés dans d̂ et restent sans danger. Seuls les biais qui varient ou un compas figé se détectent, en comparant aux fix GPS sur une base d'au moins 1 h. |
| H33 | Pannes GPS et compas | coupure 0,05/jour (médiane 2 h, σ log 1,2) ; panne définitive 0,0025/jour ; saut 0,2/jour (200–5 000 m, loi log-uniforme) ; biais compas 0,007/jour à 2°/jour (plafond 25°) ; compas figé 0,002/jour | Jugement. Ces taux sont multipliés par P15 (S9) et P18 (S12, S13, S20). |
| H34 | Sauts GPS non détectables | sous environ 500 m | Limite réelle de l'approche : un fix corrompu qui reste dans la boîte prédite est indiscernable d'un fix correct. Ce sont les seules sorties de boîte observées (environ 0,04 % des pas). |
| H35 | Mode dégradé | boîte > 20 km : cap compas fixe de 75° (ENE), puissance × 0,5 ; si le compas est déclaré HS et le GPS absent : moteur coupé, en attente d'un fix | Le cap ENE garantit une progression vers une côte large (Irlande et Royaume-Uni) sans dépendre de la position. Configurable. |
| H36 | Arrivée | homologuée seulement si le GPS fonctionne à l'entrée dans le cercle | Règle D.1 : la position doit être enregistrée dans le cercle. |
| H37 | Crabe | angle de crabe limité à 40° | Inutile de lutter contre toute la dérive : la route vers le but est recalculée à chaque pas. |

## Risques et calibration

| Id | Hypothèse | Valeur | Justification |
|---|---|---|---|
| H40 | Historique = solutions « partielles » | — | Choix de l'utilisateur (C1). L'état `absente` est donc plus risqué que l'historique. |
| H41 | Comptages | 30 tentatives ; captures 9,5 ; logiciel 8,5 ; mécanique 3,5 | Fournis par l'utilisateur ; je ne les ai pas retrouvés dans les pages lues. La page « défi » liste 8 cas (3 captures, 3 logiciels, 2 mécaniques). Prior Beta(k + ½, n − k + ½), dit de Jeffreys. |
| H42 | Réussites | 1 (SB Met 2018), plus 1 incertaine | Oshen PC13 aurait terminé une traversée Est→Ouest en septembre 2026 (liste de diffusion Microtransat, sous réserve de confirmation par le jury). |
| H43 | Exposition historique | 30 jours en mer par tentative | Sert à convertir une probabilité par mission en taux par jour. Jugement : beaucoup de tentatives ont échoué en quelques jours ou semaines. |
| H44 | Répartition des familles et probabilité de fin | logiciel : P16 45 %, P17 30 %, P18 25 % ; mécanique : P7 50 %, P6 20 %, P4 15 %, P5 15 %. Les comptages historiques sont des **fins de mission** : le taux d'occurrence vaut taux de fin / P(fin \| Pi, partielle), avec P(fin) = 1,0 (P4), 0,3 (P5), 0,3 (P6), 0,5 (P7), 0,8 (P16), 0,3 (P17), 0,5 (P18) | Cas cités par la doc : ABoat, Endeavour, Pinta pour P16 ; SB Wave pour P17 ; servo de barre de Scout pour P7. Contrôle (`python main.py calibration`, tout « partiel », départ le 15 juin, 200 runs) : fin par le logiciel 32 % [25–40 %] contre ≈ 28 % historiquement ; mécanique 6 % [2,5–10 %] contre ≈ 12 % ; captures 14 % [9–20 %] contre ≈ 32 %. L'écart sur les captures est attendu : notre route traverse le large, alors que les tentatives historiques partaient des côtes européennes, très pêchées. |
| H44b | Fins de mission « logicielles » | cap erroné ou moteur bloqué depuis plus de 5 jours → fin (P16) ; failsafe de retour actif depuis plus de 10 jours → fin (P17) ; GPS définitivement HS → arrivée impossible à prouver (P18) | Sans ces règles, un bateau rendu inutile par un bug restait en mer « en mission » jusqu'à la fin des données. |
| H45 | Pêche : exposition de référence | effort moyen sur les 1 555 premiers km de la route, soit 30 jours à 0,6 m/s | Cale le taux de rencontre pour que, à exposition historique, la fin par capture corresponde à 9,5 cas sur 30. |
| H46 | Multiplicateurs de solution | absente ×2 (facteur d'incertitude 1,5), partielle ×1, validée ×0,25 (facteur 2) ; solutions secondaires : racine carrée | Jugement. Une solution validée par S13 divise le risque par environ 4. |
| H47 | P19 / S13 (validation) | ×1,5, ×1 ou ×0,6 sur les domaines B à G | La doc présente P19 comme la cause racine invisible des autres problèmes. |
| H48 | S20 (démarche progressive) | ×1,2, ×1 ou ×0,8 sur les domaines A à G | Jugement. |
| H50 | P1 survie de la coque | 0,0004/jour à Hs 4 m, × (Hs/4)³ | Jugement, sans historique. |
| H51 | P2 chavirage | 0,02/jour à Hs 4 m, × (Hs/4)⁴ au-dessus de 3 m ; redressement 0,30 / 0,85 / 0,97 selon S1 ; 0,30 si les drains sont bouchés ; redressement tardif 0,05/jour | Jugement. **Ce modèle domine l'hiver** : c'est le premier à remettre en question. |
| H52 | P3 trappes | 0,0003/jour × (Hs/4)³, plus 25 % par chavirage | Jugement. |
| H53 | P6 hélice engagée | taux mécanique × (1 + pêche/référence), dégagement 0,15/jour, puissance utile −70 % | Jugement. |
| H54 | P8 secours de gouverne | 0 / 0,5 / 0,9 selon S5 | Jugement. |
| H55 | P9 louvoiement | perte de VMG de 25 % / 12 % / 3 % au-dessus de Hs 3 m | Jugement. |
| H56 | P10 circuit solaire | 0,002/jour par circuit ; un seul circuit si S6 est absente | Jugement. |
| H57 | P11 batterie | défaillance de cellule 0,0004/jour (capacité 50 % avec S6, 5 % sans) ; −0,05 % de capacité par Wh chargé sous 0 °C (sans S6, donc sans verrou du BMS) | Jugement, d'après l'ordre de grandeur du placage lithium. |
| H58 | P13 électronique | 0,001/jour, plus les cascades depuis P1, P3, P5 et P22 | Jugement. |
| H59 | P14 corrosion | 0,0006/jour à 30 jours, loi de Weibull k = 2,5 | Jugement : le risque croît avec le temps passé en mer. |
| H60 | P15 CEM | taux de pannes GPS et compas ×2 / ×1,3 / ×1 | Jugement. |
| H61 | P16 issues | cap erroné 45 %, moteur bloqué 30 %, gel 25 % | D'après les cas historiques (ABoat, Endeavour, Pinta). |
| H62 | P17 | taux × (1 + 0,2 × min(redémarrages, 20)) ; bug de `millis()` au 49,7e jour avec une probabilité de 0,5 / 0,15 / 0 selon S10, nulle si S13 est validée ; failsafe « retour au départ » après 48 h sans télémétrie avec une probabilité de 0,5 / 0,15 / 0 ; reprise par watchdog 0 / 0,7 / 0,98 selon S11 | Cas SB Wave. Le débordement de `millis()` est cité par la doc. |
| H63 | P20 / P21 | 0,0015/jour et 0,001/jour | Jugement. |
| H64 | P22 collision | densité GFW × largeur de 40 m × 25 km/h ; évitement grâce à l'AIS 0 / 0,5 / 0,85 ; gravité : coulé 25 %, voie d'eau 45 %, sans dégât 30 % | Jugement. |
| H65 | P23 | probabilité qu'un pêcheur laisse le bateau : 0,25 / 0,45 / 0,65 selon S15 | Jugement, d'après les cas où le bateau a été récupéré (*Breizh Spirit*, *SB Wave*). |
| H66 | P24 rencontre de pêche | sans suite 55 %, engagement 15 % (× S1·S16·S4), récupéré 30 % ; après engagement : libéré 30 %, capturé 50 %, perdu 20 % | Jugement, calé globalement sur les 9,5 captures. |
| H67 | P25 | croissance de l'encrassement ×1 / ×0,6 / ×0,25 selon S17 ; drains des ailes bouchés à 25 % | Doc P25 : les trous de vidange obstrués annulent l'auto-redressement. |
| H68 | P26 faune | 0,0003/jour ; 20 % de cascade vers P1 | Jugement. |
| H69 | P27 balise S18 | fiable à 0 / 0,7 / 0,95 | Jugement. |
| H70 | P28 naufrage après voie d'eau | 0,7 / 0,3 / 0,05 selon S1 (âme mousse) | Jugement. |
