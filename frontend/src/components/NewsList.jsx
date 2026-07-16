import React from "react";
import NewsCard from "./NewCard";

const NewsList = ({ news }) => {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
      {news.map((item) => (
        <NewsCard key={item.id ?? item.url ?? Math.random()} item={item} />
      ))}
    </div>
  );
};

export default NewsList;
