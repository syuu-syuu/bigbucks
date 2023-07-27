const path = require('path');
const { PurgeCSS } = require('purgecss');
const glob = require('glob');
const fs = require('fs');
const config = require('./purgecss.config.js');

const content = [].concat(...config.content.map(filePattern => glob.sync(path.resolve(__dirname, filePattern))));
const css = [].concat(...config.css.map(filePattern => glob.sync(path.resolve(__dirname, filePattern))));
const output = path.resolve(__dirname, config.output);

if (!fs.existsSync(output)) {
    fs.mkdirSync(output);
}

console.log('Content files:', content);
console.log('CSS files:', css);

const cssFilesData = css.map(file => ({
    raw: fs.readFileSync(file, 'utf8'),
    extension: path.extname(file),
    file: file,
}));

const purgeCSSResults = new PurgeCSS().purge({
    content: content.map(file => ({ raw: fs.readFileSync(file, 'utf8'), extension: path.extname(file), path: file })),
    css: cssFilesData,
    safelist: config.whitelist,
});

purgeCSSResults
    .then((results) => {
        console.log('PurgeCSS results:', results);
        results.forEach((result, index) => {
            const cssFilePath = cssFilesData[index].file;
            if (cssFilePath) {
                const outputPath = path.join(output, path.basename(cssFilePath));
                console.log('Purified CSS:', outputPath);
                fs.writeFileSync(outputPath, result.css, 'utf8');
            }
        });
    })
    .catch((err) => {
        console.error('Error during PurgeCSS:', err);
    });
