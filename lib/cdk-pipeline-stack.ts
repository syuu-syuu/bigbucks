import { CodePipeline, CodePipelineSource, ShellStep } from 'aws-cdk-lib/pipelines';
import { Construct } from 'constructs';
import { Stack, StackProps } from 'aws-cdk-lib';
import { CdkEBStage } from './eb-stage';


export class CdkPipelineStack extends Stack {
    constructor(scope: Construct, id: string, props?: StackProps) {
        super(scope, id, props);

        const pipeline = new CodePipeline(this, 'Pipeline', {
            pipelineName: 'MyServicePipeline',
            synth: new ShellStep('Synth', {
                input: CodePipelineSource.gitHub('syuu-syuu/bigbucks', 'master'),
                installCommands: ['npm i -g npm@latest'],
                commands: ['npm ci', 'npm run build', 'npx cdk synth'],
            }),
        });

        // This is where we add the application stages
        // deploy beanstalk app
        // For environment with all default values:
        // const deploy = new CdkEBStage(this, 'Pre-Prod');

        // For environment with custom AutoScaling group configuration
        const deploy = new CdkEBStage(this, 'Pre-Prod', {
            minSize: "1",
            maxSize: "2"
        });
        const deployStage = pipeline.addStage(deploy); 
        
    }
}
