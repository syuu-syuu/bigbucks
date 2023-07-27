module.exports = {
    content: [
        './bigbucks/**/*.html', // Match all HTML files
        './bigbucks/**/*.js', // Match all JavaScript files
    ],
    css: [
        './bigbucks/static/css/*.css', // Match all CSS files
    ],
    output: './purified/', // Output directory
    whitelist: [], // Add whitelist class names if needed
};
