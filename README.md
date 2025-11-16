# Descrizione
Questo progetto implementa un sistema di comunicazione basato su socket TCP (stream socket) utilizzando il modulo socket di Python. L’obiettivo è realizzare un canale affidabile per lo scambio di dati tra un client e un server, sfruttando le caratteristiche del protocollo TCP, come ordinamento dei pacchetti, controllo degli errori e gestione automatica della connessione.

# Funzionalità
Il server crea una socket in ascolto su una porta definita, accetta le richieste di connessione dei client e gestisce la comunicazione inviando o ricevendo dati secondo la logica applicativa prevista. Il client stabilisce la connessione verso il server e interagisce attraverso messaggi testuali o binari, a seconda delle necessità.

# Finalità
Il progetto è pensato come base per applicazioni di rete più complesse, come chat, sistemi di trasferimento file, servizi remoti personalizzati o protocolli applicativi dedicati. L'implementazione è modulare e facilmente estendibile, consentendo di migliorare sicurezza, prestazioni e gestione delle connessioni multiple (es. tramite threading, multiprocessing o async I/O).
