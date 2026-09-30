---
id: 7553
severity: "High"
---

# No protection implemented against listing clone NFTs

## Description

Any malicious seller can copy the name, symbol and description of any previously listed asset and list it at a 1 wei lower price. In the case of this NFT being selected to be purchased by the system, this malicious seller will guarantee that their asset with lower price would be selected. This will lead to user's copying previously listed NFT's and listing it at a lower price, in a way creating a price race to the bottom.

Any seller can list an NFT with the list function.
```solidity
function list(string calldata name, string calldata symbol, bytes calldata desc, uint256 price, address _buyer)
    external
{
    BuyerAgent buyer = BuyerAgent(_buyer);
    (uint256 round, BuyerAgent.Phase phase,) = buyer.getRoundPhase();

    // buyer must be in the sell phase
    if (phase != BuyerAgent.Phase.Sell) {
        revert BuyerAgent.InvalidPhase(phase, BuyerAgent.Phase.Sell);
    }
    // asset count must not exceed maxAssetCount
    if (getCurrentMarketParameters().maxAssetCount == assetsPerBuyerRound[_buyer][round].length) {
        revert AssetLimitExceeded(getCurrentMarketParameters().maxAssetCount);
    }

    // all is well, create the asset & its listing
    address asset = address(swanAssetFactory.deploy(name, symbol, _desc, msg.sender));
    listings[asset] = AssetListing({
        createdAt: block.timestamp,
        royaltyFee: buyer.royaltyFee(),
        price: _price,
        seller: msg.sender,
        status: AssetStatus.Listed,
        buyer: _buyer,
        round: round
    });

    // add this to list of listings for the buyer for this round
    assetsPerBuyerRound[_buyer][round].push(asset);

    // transfer royalties
    transferRoyalties(listings[asset]);

    emit AssetListed(msg.sender, asset, _price);
}
```
As observed, this function take the name, symbol, desc and price parameters. Function then deploys a new NFT with these parameters and mints 1 NFT to the msg.sender.
```solidity
contract SwanAssetFactory {
    /// @notice Deploys a new SwanAsset token.
    function deploy(string memory name, string memory symbol, bytes memory description, address owner)
        external
        returns (SwanAsset)
    {
        return new SwanAsset(name, symbol, description, owner, msg.sender);
    }
}

/// @notice SwanAsset is an ERC721 token with a single token supply.
contract SwanAsset is ERC721, Ownable {
    /// @notice Creation time of the token
    uint256 public createdAt;
    /// @notice Description of the token
    bytes public description;

    /// @notice Constructor sets properties of the token.
    constructor(
        string memory _name,
        string memory _symbol,
        bytes memory _description,
        address _owner,
        address _operator
    ) ERC721(name, symbol) Ownable(_owner) {
        description = _description;
        createdAt = block.timestamp;

        // owner is minted the token immediately
        ERC721.mint(owner, 1);

        // Swan (operator) is approved to by the owner immediately.
        ERC721.setApprovalForAll(owner, _operator, true);
    }
}
```
As observed, there are no checks for "clone" inputs. Meaning that any malicious seller can copy the parameters of any previously listed NFT and list it at a 1 wei lower price. In case of an NFT with these parameters being selected, the malicious user would guarantee their NFT at lower price would be selected, putting no work in creating an original NFT and simply copying previously deployed NFTs. This will create a price race to the bottom among users where users would list the NFT with same parameters, each one putting it at 1 wei lower price, breaking the protocols intended use. The AI agents seeing all or most of the NFT's listed having the same properties would choose to purchase the NFT with these properties at the lowest price.

Impact: High, this vulnerability will break the intended use of the protocol. It will create a price race to the bottom where users list the NFT with same name, symbol and description, each user listing it at 1 wei lower price to ensure their NFT would be chosen by the system. Likelihood: Low, There are no guarantees that this NFT would be chosen by the system but noticing copies of the same NFTs can manipulate the LLM into thinking this is a good purchase.

## Proof of Concept

no poc

## Recommendation

Implement a for loop in the list function that will check the NFT that is being listed against the already listed NFTs. An example for loop is shown below. Keep in mind that this implementation might cost a lot of gas if there are too many listed NFTs.
```solidity
address[] memory assets = assetsPerBuyerRound[buyer][round];
for (uint256 i = 0; i < assets.length; i++) {
    IERC721 asset = IERC721(assets[i]);
    
    // Retrieve the name and symbol from the asset contract
    string memory assetName = asset.name();
    string memory assetSymbol = asset.symbol();
    
    // Check if both name and symbol match
    if (keccak256(bytes(assetName)) == keccak256(bytes(targetName)) &&
        keccak256(bytes(assetSymbol)) == keccak256(bytes(targetSymbol))) {
        revert("Asset with matching name and symbol already exists in this round");
    }
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a lack of uniqueness enforcement when an NFT is listed on the marketplace. The list function accepts arbitrary name, symbol and description values and deploys a new ERC‑721 token with those parameters, but it never checks whether an identical asset has already been listed in the same round. Because the selection algorithm prefers the lowest price, a malicious seller can copy the metadata of any previously listed NFT, deploy a clone contract, and list it for just one wei less than the original. When the system evaluates the pool of candidates, the cloned asset will be chosen, allowing the attacker to capture the sale without creating any original content. This situation can occur whenever a seller calls the list function during the Sell phase; there are no additional guards such as metadata hashing, creator address verification, or per‑round uniqueness constraints. The impact is that the protocol’s core promise of unique, creator‑driven NFTs is broken: users see multiple listings with identical name, symbol and description, each undercutting the previous price, leading to a race‑to‑the‑bottom where the cheapest clone wins. From a user’s perspective the UI may display many entries that look the same, and the expected unique artwork is replaced by a duplicate that costs almost nothing, causing confusion and potential loss of value. The issue was discovered during a manual audit that examined the list function’s logic and noticed the absence of any duplicate‑detection mechanism. It can be hard to notice because the cloned NFTs are syntactically valid and the price difference is minimal, so automated tools may not flag them as malicious. To remediate, the contract should enforce that each asset’s metadata (or a hash of it) is unique within a round, reject listings that match an existing name‑symbol pair, or require the original creator’s address to be recorded and checked. Implementing a loop that scans existing listings or, more efficiently, maintaining a mapping of metadata hashes to prevent duplicates would close the attack surface, albeit with some gas cost considerations. In summary, the bug belongs to the class of duplicate‑asset or clone‑listing vulnerabilities, where insufficient validation allows adversaries to undercut genuine listings, violating the protocol’s accounting assumptions and expected economic behavior.
