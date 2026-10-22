import { TelegramClient } from "telegram";
import { StringSession } from "telegram/sessions/index.js";
import fs from "fs";


const apiId = Number(process.env.TELEGRAM_API_ID);
const apiHash = process.env.TELEGRAM_API_HASH;

const session = new StringSession(
    process.env.TELEGRAM_SESSION
);


const CHANNEL = "YOUR_GROUP_USERNAME";


const client = new TelegramClient(
    session,
    apiId,
    apiHash,
    {
        connectionRetries: 5
    }
);



function readJSON(file){

    return JSON.parse(
        fs.readFileSync(file,"utf8")
    );

}


function saveJSON(file,data){

    fs.writeFileSync(
        file,
        JSON.stringify(
            data,
            null,
            2
        )
    );

}



async function main(){

    await client.start({
        botAuthToken: false
    });


    console.log("Connected");


    let quizzes =
        readJSON("quizzes.json");


    let metadata =
        readJSON("metadata.json");



    const messages =
        await client.getMessages(
            CHANNEL,
            {
                limit: 100
            }
        );



    for(const msg of messages){


        if(!msg.poll)
            continue;



        const poll =
            msg.poll;



        if(poll.id === undefined)
            continue;



        if(
          metadata.poll_ids.includes(
              poll.id.toString()
          )
        ){
            continue;
        }



        const question =
            poll.question;



        const options =
            poll.answers.map(
                x => x.text
            );



        const correct =
            poll.correctAnswers
            ?
            poll.correctAnswers[0]
            :
            0;



        const explanation =
            poll.explanation || "";



        const quiz = [

            question,

            options,

            correct,

            explanation

        ];



        quizzes.push(quiz);



        metadata.poll_ids.push(
            poll.id.toString()
        );



        console.log(
            "Added:",
            question
        );


    }



    saveJSON(
        "quizzes.json",
        quizzes
    );


    saveJSON(
        "metadata.json",
        metadata
    );


    await client.disconnect();

}



main();
